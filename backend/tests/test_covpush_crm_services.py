"""Coverage-push tests for CRM integration services (target >=95% lines).

Covers:
- integrations/atom_hubspot_integration_service.py
- integrations/hubspot_routes.py
- integrations/hubspot_service.py
- integrations/atom_zendesk_integration_service.py
- integrations/freshdesk_service.py
- integrations/salesforce_routes.py
- integrations/jira_service.py
- integrations/trello_service.py
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


def _http_resp(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = Mock()
    if json_data is not None:
        resp.json = Mock(return_value=json_data)
    else:
        resp.json = Mock(return_value={})
    resp.text = "{}"
    return resp


def _acm(post_result=None, get_result=None, put_result=None, delete_result=None):
    client = MagicMock()
    client.post = AsyncMock(return_value=post_result or _http_resp(200, {}))
    client.get = AsyncMock(return_value=get_result or _http_resp(200, {}))
    client.put = AsyncMock(return_value=put_result or _http_resp(200, {}))
    client.delete = AsyncMock(return_value=delete_result or _http_resp(204, {}))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ============================================================================
# hubspot_service.py
# ============================================================================

class TestHubspotService:
    def make(self, config=None):
        import integrations.hubspot_service as hs

        svc = hs.HubSpotService(config=config)
        svc.http = MagicMock()
        for m in ("get", "post", "patch"):
            setattr(svc.http, m, AsyncMock(return_value=_http_resp(200, {"results": [], "campaigns": [], "total": 0})))
        return svc

    @pytest.mark.asyncio
    async def test_capabilities_and_close(self):
        import integrations.hubspot_service as hs

        svc = hs.HubSpotService(config={"access_token": "t"})
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert caps["required_params"] == ["access_token"]
        await svc.close()

    @pytest.mark.asyncio
    async def test_execute_operation_dispatch(self):
        svc = self.make({"access_token": "t"})
        with patch.object(svc, "execute_entity_operation", new=AsyncMock(return_value={"success": True})), \
             patch.object(svc, "search_content", new=AsyncMock(return_value={"hits": []})):
            assert (await svc.execute_operation("create_contact", {}))["success"]
            assert (await svc.execute_operation("get_contacts", {}))["success"]
            assert (await svc.execute_operation("list_contacts", {}))["success"]
            assert (await svc.execute_operation("get_companies", {}))["success"]
            assert (await svc.execute_operation("get_deals", {}))["success"]
            r = await svc.execute_operation("search_content", {"query": "x"})
            assert r["success"]
            r = await svc.execute_operation("nope", {})
            assert not r["success"]

    @pytest.mark.asyncio
    async def test_execute_operation_tenant_mismatch_and_error(self):
        svc = self.make({"access_token": "t"})
        r = await svc.execute_operation("get_contacts", {}, context={"tenant_id": "other"})
        assert not r["success"]
        with patch.object(svc, "execute_entity_operation", new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = await svc.execute_operation("get_contacts", {})
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_execute_entity_operation_all_branches(self):
        svc = self.make({"access_token": "t"})
        with patch.object(svc, "create_contact", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_contact", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_contacts", new=AsyncMock(return_value=[])), \
             patch.object(svc, "create_company", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_company", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_companies", new=AsyncMock(return_value=[])), \
             patch.object(svc, "create_deal", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_deal", new=AsyncMock(return_value={})), \
             patch.object(svc, "get_deals", new=AsyncMock(return_value=[])):
            for ent in ("contact", "company", "deal"):
                assert (await svc.execute_entity_operation("create", ent, {}))["success"]
                assert (await svc.execute_entity_operation("get", ent, {}))["success"]
                assert (await svc.execute_entity_operation("list", ent, {}))["success"]
                r = await svc.execute_entity_operation("delete", ent, {})
                assert not r["success"]
            r = await svc.execute_entity_operation("list", "widget", {})
            assert not r["success"]

    @pytest.mark.asyncio
    async def test_authenticate(self):
        svc = self.make({"access_token": "t"})
        svc.http.post = AsyncMock(return_value=_http_resp(200, {"access_token": "newtok"}))
        data = await svc.authenticate("cid", "secret", "uri", "code")
        assert data["access_token"] == "newtok"
        assert svc.access_token == "newtok"
        from fastapi import HTTPException
        import httpx
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException) as ei:
            await svc.authenticate("cid", "secret", "uri", "code")
        assert ei.value.status_code == 400
        svc.http.post = AsyncMock(side_effect=RuntimeError("y"))
        with pytest.raises(HTTPException) as ei:
            await svc.authenticate("cid", "secret", "uri", "code")
        assert ei.value.status_code == 500

    @pytest.mark.asyncio
    async def test_get_contacts_companies_deals_campaigns(self):
        svc = self.make({"access_token": "t"})
        from fastapi import HTTPException
        import httpx

        svc.http.get = AsyncMock(return_value=_http_resp(200, {"results": [{"id": "1"}], "campaigns": [{"id": "c"}]}))
        assert await svc.get_contacts(limit=5, offset=10) == [{"id": "1"}]
        assert await svc.get_companies(limit=5, offset=1) == [{"id": "1"}]
        assert await svc.get_deals(limit=5, offset=2) == [{"id": "1"}]
        assert await svc.get_campaigns(limit=5, offset=1) == [{"id": "c"}]

        bare = self.make({"access_token": None})
        bare.http.get = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await bare.get_contacts(token=None)
        with pytest.raises(HTTPException):
            await bare.get_companies(token=None)
        with pytest.raises(HTTPException):
            await bare.get_deals(token=None)
        with pytest.raises(HTTPException):
            await bare.get_campaigns(token=None)

        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "envtok"}):
            svc.http.get = AsyncMock(side_effect=httpx.HTTPError("boom"))
            with pytest.raises(HTTPException):
                await svc.get_contacts(token=None)

    @pytest.mark.asyncio
    async def test_search_content(self):
        from fastapi import HTTPException
        import httpx

        svc = self.make({"access_token": "t"})
        svc.http.post = AsyncMock(return_value=_http_resp(200, {"total": 3}))
        assert (await svc.search_content("q"))["total"] == 3

        bare = self.make({"access_token": None})
        with patch.dict("os.environ", {}, clear=False):
            bare.access_token = None
            with pytest.raises(HTTPException):
                await bare.search_content("q")
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.search_content("q")

    @pytest.mark.asyncio
    async def test_create_contact_company_deal(self):
        from fastapi import HTTPException
        import httpx

        svc = self.make({"access_token": "t"})
        svc.http.post = AsyncMock(return_value=_http_resp(201, {"id": "1"}))
        assert (await svc.create_contact("a@b.c", first_name="A", phone="555"))["id"] == "1"
        assert (await svc.create_company("Acme", domain="acme.com"))["id"] == "1"
        assert (await svc.create_deal("Deal", 100.0, company_id="9"))["id"] == "1"
        assert (await svc.create_deal("Deal", 100.0))["id"] == "1"

        svc.http.post = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.create_contact("a@b.c")
        with pytest.raises(HTTPException):
            await svc.create_company("Acme")
        with pytest.raises(HTTPException):
            await svc.create_deal("D", 1.0)
        with pytest.raises(HTTPException):
            await self.make({"access_token": None}).create_contact("a@b.c")
        with pytest.raises(HTTPException):
            await self.make({"access_token": None}).create_company("Acme")
        with pytest.raises(HTTPException):
            await self.make({"access_token": None}).create_deal("D", 1.0)

    @pytest.mark.asyncio
    async def test_get_object_and_update_object(self):
        from fastapi import HTTPException
        import httpx

        svc = self.make({"access_token": "t"})
        svc.http.get = AsyncMock(return_value=_http_resp(200, {"id": "1"}))
        svc.http.patch = AsyncMock(return_value=_http_resp(200, {"id": "1"}))
        assert (await svc.get_contact("1"))["id"] == "1"
        assert (await svc.get_company("1"))["id"] == "1"
        assert (await svc.get_deal("1"))["id"] == "1"
        assert (await svc.update_contact("1", {"a": 1}))["id"] == "1"
        assert (await svc.update_deal("1", {"a": 1}))["id"] == "1"

        with pytest.raises(HTTPException):
            await self.make({"access_token": None}).get_object("contacts", "1")
        svc.http.get = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.get_object("contacts", "1")
        with pytest.raises(HTTPException):
            await self.make({"access_token": None}).update_object("contacts", "1", {})
        svc.http.patch = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.update_object("contacts", "1", {})

    @pytest.mark.asyncio
    async def test_get_analytics_and_properties(self):
        svc = self.make({"access_token": "t"})
        with patch.object(svc, "get_deals", new=AsyncMock(return_value=[
            {"properties": {"amount": "100.5"}}, {"properties": {"amount": None}}
        ])):
            svc.http.post = AsyncMock(return_value=_http_resp(200, {"total": 7}))
            a = await svc.get_analytics()
        assert a["total_revenue"] == 100.5
        assert a["contact_count"] == 7
        assert a["deal_count"] == 2

        svc.http.post = AsyncMock(return_value=_http_resp(500, {}))
        a = await svc.get_analytics()
        assert a["contact_count"] == 0

        bare = self.make({"access_token": None})
        r = await bare.get_analytics()
        assert r["error"] == "Not authenticated"

        with patch.object(svc, "get_deals", new=AsyncMock(side_effect=RuntimeError("boom"))):
            r = await svc.get_analytics()
        assert "error" in r

        svc.http.get = AsyncMock(return_value=_http_resp(200, {"results": [{"name": "email"}]}))
        assert await svc.get_properties("contacts") == [{"name": "email"}]
        svc.http.get = AsyncMock(side_effect=RuntimeError("boom"))
        assert await svc.get_properties("contacts") == []
        assert await self.make({"access_token": None}).get_properties("contacts") == []

    @pytest.mark.asyncio
    async def test_health_check_and_sync(self):
        svc = self.make({"access_token": "t"})
        r = await svc.health_check()
        assert r["ok"] is True and r["status"] == "healthy"

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = [None, Mock(), None]
        existing = MagicMock()
        db.query.return_value.filter_by.return_value.first.side_effect = [None, existing, None]
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_analytics", new=AsyncMock(return_value={
                 "contact_count": 1, "deal_count": 2, "total_revenue": 3.0})):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert r["success"] is True and r["metrics_synced"] == 3

        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db2), \
             patch.object(svc, "get_analytics", new=AsyncMock(return_value={})):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert not r["success"]

        with patch.object(svc, "get_analytics", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert not r["success"]

        with patch.object(svc, "sync_to_postgres_cache", new=AsyncMock(return_value={"success": True})):
            r = await svc.full_sync("ws-1")
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_get_operations_and_singleton(self):
        import integrations.hubspot_service as hs

        svc = self.make({"access_token": "t"})
        ops = svc.get_operations()
        assert ops[0]["name"] == "create_contact"

        hs._hubspot_service_singleton = None
        assert hs.get_hubspot_service() is None
        with patch.dict("os.environ", {"HUBSPOT_ACCESS_TOKEN": "envtok"}):
            s1 = hs.get_hubspot_service()
            assert s1 is not None
            assert hs.get_hubspot_service() is s1
        hs._hubspot_service_singleton = None


# ============================================================================
# hubspot_routes.py
# ============================================================================

class TestHubspotRoutes:
    @pytest.mark.asyncio
    async def test_start_oauth(self):
        import integrations.hubspot_routes as routes

        with patch.dict("os.environ", {"HUBSPOT_CLIENT_ID": ""}):
            r = await routes.start_oauth()
            assert r["ok"] is False
        with patch.dict("os.environ", {"HUBSPOT_CLIENT_ID": "cid"}):
            r = await routes.start_oauth()
            assert r["ok"] is True and "auth_url" in r

    @pytest.mark.asyncio
    async def test_oauth_callback_route(self):
        import integrations.hubspot_routes as routes

        req = routes.HubSpotAuthRequest(client_id="c", client_secret="s",
                                        redirect_uri="http://x", code="code")
        with patch.object(routes.HubSpotService, "authenticate",
                          new=AsyncMock(return_value={"access_token": "t"})):
            r = await routes.hubspot_auth(req)
        assert r["access_token"] == "t"

    @pytest.mark.asyncio
    async def test_get_contacts_companies_deals_campaigns_lists_routes(self):
        import integrations.hubspot_routes as routes

        svc = MagicMock()
        svc.get_contacts_wrapper = AsyncMock(return_value=[{"id": "1"}])
        svc.get_companies = AsyncMock(return_value=[{"id": "1"}])
        svc.get_deals_wrapper = AsyncMock(return_value=[{"id": "1"}])
        svc.get_campaigns = AsyncMock(return_value=[{"id": "1"}])
        svc.get_lists = AsyncMock(return_value=[{"id": "1"}])
        with patch.object(routes, "HubSpotService", return_value=svc):
            assert (await routes.get_contacts()) == [{"id": "1"}]
            assert (await routes.get_companies()) == [{"id": "1"}]
            assert (await routes.get_deals()) == [{"id": "1"}]
            assert (await routes.get_campaigns()) == [{"id": "1"}]
            assert (await routes.get_lists()) == [{"id": "1"}]

    @pytest.mark.asyncio
    async def test_search_create_routes(self):
        import integrations.hubspot_routes as routes

        svc = MagicMock()
        svc.search_content = AsyncMock(return_value=SimpleNamespace(results=[], total=0))
        svc.create_contact = AsyncMock(return_value={"id": "1"})
        svc.create_deal = AsyncMock(return_value={"id": "1"})
        with patch.object(routes, "HubSpotService", return_value=svc):
            req = routes.HubSpotSearchRequest(query="q")
            r = await routes.search_content(req)
            assert r.total == 0
            c = routes.HubSpotContactCreate(email="a@b.c")
            assert (await routes.create_contact(c))["id"] == "1"
            d = routes.HubSpotDealCreate(deal_name="D", stage="x", pipeline="p")
            assert (await routes.create_deal(d))["id"] == "1"

    @pytest.mark.asyncio
    async def test_stats_analytics_routes(self):
        import integrations.hubspot_routes as routes

        adv = MagicMock()
        adv.analytics_metrics = {
            "total_contacts": 1, "total_companies": 2, "total_deals": 3,
            "total_campaigns": 4, "active_deals": 5, "won_deals": 6,
            "lost_deals": 7, "total_revenue": 8.0,
            "win_rate": 9.0, "monthly_revenue": 10.0, "top_campaigns": [],
            "recent_activities": [], "pipeline_stages": [],
        }
        svc = MagicMock()
        svc.advanced_service = adv
        svc.get_stats = AsyncMock(return_value=routes.HubSpotStats(
            total_contacts=1, total_companies=2, total_deals=3, total_campaigns=4,
            active_deals=5, won_deals=6, lost_deals=7, total_revenue=8.0))
        with patch.object(routes, "HubSpotService", return_value=svc):
            stats = await routes.get_stats()
            assert stats.total_contacts == 1
            analytics = await routes.get_analytics()
            assert analytics.totalContacts == 1

        svc2 = MagicMock()
        svc2.advanced_service = None
        svc2.get_stats = AsyncMock(return_value=routes.HubSpotStats(
            total_contacts=1500, total_companies=250, total_deals=75, total_campaigns=12,
            active_deals=45, won_deals=20, lost_deals=10, total_revenue=1250000.0))
        with patch.object(routes, "HubSpotService", return_value=svc2):
            stats = await routes.get_stats()
            assert stats.total_contacts == 1500
            analytics = await routes.get_analytics()
            assert analytics.totalContacts == 1547
            assert len(analytics.topPerformingCampaigns) == 3

    @pytest.mark.asyncio
    async def test_ai_routes(self):
        import integrations.hubspot_routes as routes

        adv = MagicMock()
        adv.analytics_metrics = {}
        svc = MagicMock()
        svc.advanced_service = adv
        with patch.object(routes, "HubSpotService", return_value=svc):
            r = await routes.get_ai_predictions()
            assert len(r.models) == 3
            req = routes.AIAnalyzeLeadRequest(contact_id="1")
            out = await routes.analyze_lead(req)
            assert 0 <= out.leadScore <= 100

        adv._score_lead = AsyncMock(side_effect=RuntimeError("boom"))
        with patch.object(routes, "HubSpotService", return_value=svc):
            req = routes.AIAnalyzeLeadRequest(contact_id="1")
            out = await routes.analyze_lead(req)
            assert 0 <= out.leadScore <= 100

        svc_none = MagicMock()
        svc_none.advanced_service = None
        with patch.object(routes, "HubSpotService", return_value=svc_none):
            req = routes.AIAnalyzeLeadRequest(contact_id="1")
            out = await routes.analyze_lead(req)
            assert 0 <= out.leadScore <= 100

    @pytest.mark.asyncio
    async def test_health_root(self):
        import integrations.hubspot_routes as routes

        svc = MagicMock()
        svc.health_check_wrapper = AsyncMock(return_value={"ok": True})
        with patch.object(routes, "HubSpotService", return_value=svc):
            r = await routes.health_check()
            assert r["ok"] is True
        r = await routes.hubspot_root()
        assert r["service"] == "hubspot"


# ============================================================================
# jira_service.py
# ============================================================================

class TestJiraService:
    def make(self, config=None):
        from integrations.jira_service import JiraService

        return JiraService(config=config or {})

    def test_init_branches(self):
        from integrations.jira_service import JiraService

        with patch.dict("os.environ", {}, clear=False):
            s1 = JiraService(config={"access_token": "t", "cloud_id": "cloud12345"})
            assert "cloud12345" in s1.base_url
            s2 = JiraService(config={"base_url": "https://jira.example.com",
                                     "username": "u", "api_token": "p"})
            assert s2.session.headers["Authorization"].startswith("Basic")
            s3 = JiraService(config={})
            assert s3.base_url is None
            with pytest.raises(ValueError):
                JiraService(config={"base_url": "http://169.254.169.254"})

    def test_make_request_with_token(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        svc.session.request = Mock(return_value=_http_resp(200, {}))
        svc._make_request("GET", "/rest/api/3/project", token="tok")
        headers = svc.session.request.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer tok"

    def test_test_connection(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        svc.session.get = Mock(return_value=_http_resp(200, {"displayName": "Bob", "emailAddress": "b@x.com"}))
        r = svc.test_connection()
        assert r["status"] == "success" and r["user"] == "Bob"
        svc.session.get = Mock(return_value=_http_resp(401, {}))
        r = svc.test_connection()
        assert r["status"] == "error"
        svc.session.get = Mock(side_effect=RuntimeError("x"))
        r = svc.test_connection()
        assert r["status"] == "error"

    def test_crud_methods(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        svc.session.request = Mock(return_value=_http_resp(200, {"values": [1], "total": 5,
                                                                  "issues": [], "comments": [{"id": 1}],
                                                                  "worklogs": [{"id": 1}], "transitions": []}))
        assert svc.get_projects()["values"] == [1]
        assert svc.get_project("KEY")["values"] == [1]
        assert svc.search_issues("jql")["total"] == 5
        assert svc.search_issues("jql", fields=["summary"])["total"] == 5
        assert svc.get_issue("KEY-1")["values"] == [1]
        assert svc.create_issue("KEY", "Sum", "Task", priority="High", assignee="a")["values"] == [1]
        assert svc.create_issue("KEY", "Sum", "Task")["values"] == [1]
        assert svc.update_issue("KEY-1", {"fields": {}}) is True
        assert svc.add_comment("KEY-1", "hello")["values"] == [1]
        assert svc.get_comments("KEY-1") == [{"id": 1}]
        assert svc.get_users("KEY")["values"] == [1]
        assert svc.get_users()["values"] == [1]
        assert svc.get_statuses("KEY")["values"] == [1]
        assert svc.get_issue_types("KEY")["values"] == [1]
        assert svc.get_issue_types()["values"] == [1]
        assert svc.get_worklogs("KEY-1") == [{"id": 1}]
        assert svc.add_worklog("KEY-1", "1h", started="2026-01-01")["values"] == [1]
        assert svc.add_worklog("KEY-1", "1h")["values"] == [1]
        assert svc.get_project_components("KEY")["values"] == [1]

    def test_transition_and_assign(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        svc.session.request = Mock(return_value=_http_resp(200, {
            "transitions": [{"id": "11", "name": "Done"}, {"id": "12", "name": "In Progress"}]
        }))
        assert svc.transition_issue("KEY-1", "done", comment="nice") is True
        assert svc.transition_issue("KEY-1", "In Progress") is True
        assert svc.transition_issue("KEY-1", "Nowhere") is False
        assert svc.assign_issue("KEY-1", "bob") is True

    def test_error_paths(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        svc.session.request = Mock(side_effect=RuntimeError("x"))
        assert svc.get_projects() == []
        assert svc.get_project("K") is None
        assert svc.search_issues("jql") == {"issues": [], "total": 0, "startAt": 0, "maxResults": 0}
        assert svc.get_issue("K") is None
        assert svc.create_issue("K", "S", "T") is None
        assert svc.update_issue("K", {}) is False
        assert svc.add_comment("K", "c") is None
        assert svc.get_comments("K") == []
        assert svc.transition_issue("K", "x") is False
        assert svc.assign_issue("K", "x") is False
        assert svc.get_users() == []
        assert svc.get_statuses("K") == []
        assert svc.get_issue_types() == []
        assert svc.get_worklogs("K") == []
        assert svc.add_worklog("K", "1h") is None
        assert svc.get_project_components("K") == []

    @pytest.mark.asyncio
    async def test_sync_and_full_sync(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        with patch.object(svc, "search_issues", return_value={"total": 10}):
            db = MagicMock()
            db.query.return_value.filter_by.return_value.first.return_value = None
            with patch("core.database.SessionLocal", return_value=db):
                r = await svc.sync_to_postgres_cache("KEY")
        assert r["success"] is True and r["metrics_synced"] == 3

        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("db down")
        with patch.object(svc, "search_issues", return_value={"total": 0}), \
             patch("core.database.SessionLocal", return_value=db2):
            r = await svc.sync_to_postgres_cache("KEY")
        assert not r["success"]

        with patch.object(svc, "search_issues", side_effect=RuntimeError("x")):
            r = await svc.sync_to_postgres_cache("KEY")
        assert not r["success"]

        with patch.object(svc, "sync_to_postgres_cache", new=AsyncMock(return_value={"success": True})):
            r = await svc.full_sync("KEY")
        assert r["success"] is True

    def test_health_check_and_capabilities(self):
        svc = self.make({})
        r = svc.health_check()
        assert r["healthy"] is False
        svc.base_url = "https://jira.example.com"
        svc.session.get = Mock(return_value=_http_resp(200, {"displayName": "Bob"}))
        assert svc.health_check()["healthy"] is True
        svc.session.get = Mock(return_value=_http_resp(401, {}))
        assert svc.health_check()["healthy"] is False
        svc.session.get = Mock(side_effect=RuntimeError("x"))
        assert svc.health_check()["healthy"] is False
        assert svc.get_capabilities()["supports_webhooks"] is True

    @pytest.mark.asyncio
    async def test_execute_entity_operation(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        with patch.object(svc, "create_issue", return_value={"id": "1"}), \
             patch.object(svc, "get_issue", return_value={"id": "1"}), \
             patch.object(svc, "search_issues", return_value={"issues": []}):
            r = await svc.execute_entity_operation("create", "issue", {"project_key": "K"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("create", "issue", {"project": "K"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("get", "issue", {"issue_key": "K-1"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("get", "issue", {"id": "K-1"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("get", "issue", {})
            assert not r["success"]
            r = await svc.execute_entity_operation("list", "issue", {"jql": "x"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("list", "issue", {"project_key": "K"})
            assert r["success"] is True
            r = await svc.execute_entity_operation("list", "issue", {})
            assert r["success"] is True
            r = await svc.execute_entity_operation("delete", "issue", {})
            assert not r["success"]
            r = await svc.execute_entity_operation("create", "sprint", {})
            assert not r["success"]

    @pytest.mark.asyncio
    async def test_execute_operation_and_ops(self):
        svc = self.make({"base_url": "https://jira.example.com"})
        with patch.object(svc, "create_issue", return_value={"id": "1"}), \
             patch.object(svc, "search_issues", return_value={"issues": []}), \
             patch.object(svc, "update_issue", return_value=True), \
             patch.object(svc, "get_projects", return_value=[]), \
             patch.object(svc, "add_comment", return_value={"id": 9}):
            r = await svc.execute_operation("create_issue", {"project_key": "K"})
            assert r["success"] is True
            r = await svc.execute_operation("search_issues", {})
            assert r["success"] is True
            r = await svc.execute_operation("update_issue", {"issue_key": "K"})
            assert r["success"] is True
            r = await svc.execute_operation("get_projects", {})
            assert r["success"] is True
            r = await svc.execute_operation("add_comment", {})
            assert r["success"] is True
            r = await svc.execute_operation("bogus", {})
            assert not r["success"]
            r = await svc.execute_operation("create_issue", {}, context={"tenant_id": "other"})
            assert not r["success"]
        with patch.object(svc, "create_issue", return_value=None):
            r = await svc.execute_operation("create_issue", {"project_key": "K"})
            assert not r["success"]
        with patch.object(svc, "update_issue", return_value=False):
            r = await svc.execute_operation("update_issue", {"issue_key": "K"})
            assert not r["success"]
        with patch.object(svc, "add_comment", return_value=None):
            r = await svc.execute_operation("add_comment", {})
            assert not r["success"]
        with patch.object(svc, "create_issue", side_effect=RuntimeError("x")):
            r = await svc.execute_operation("create_issue", {})
            assert not r["success"]

    def test_get_jira_service(self):
        from integrations import jira_service as js

        js._jira_service_singleton = None
        assert js.get_jira_service() is None
        with patch.dict("os.environ", {"JIRA_API_TOKEN": "t", "JIRA_BASE_URL": "https://x"}):
            s = js.get_jira_service()
            assert s is not None
            assert js.get_jira_service() is s
        js._jira_service_singleton = None


# ============================================================================
# trello_service.py
# ============================================================================

class TestTrelloService:
    def make(self, config=None):
        from integrations.trello_service import TrelloService

        return TrelloService(config=config or {"api_key": "k", "access_token": "t"})

    def test_init_disabled(self):
        from integrations.trello_service import TrelloService

        s = TrelloService(config={})
        assert s.enabled is False
        with pytest.raises(ValueError):
            s._make_request("GET", "/members/me")
        s2 = TrelloService(config={"api_key": "k", "token": "t"})
        assert s2.enabled is True

    def test_make_request_absolute_url(self):
        svc = self.make()
        svc.session.request = Mock(return_value=_http_resp(200, {}))
        svc._make_request("GET", "https://other.trello.com/1/x", params={"a": 1})
        args = svc.session.request.call_args
        assert args.kwargs["params"]["key"] == "k"
        assert args.kwargs["url"] == "https://other.trello.com/1/x"

    def test_test_connection(self):
        svc = self.make()
        svc.session.request = Mock(return_value=_http_resp(200, {"username": "bob", "fullName": "Bob"}))
        r = svc.test_connection()
        assert r["status"] == "success"
        svc.session.request = Mock(return_value=_http_resp(401, {}))
        assert svc.test_connection()["status"] == "error"
        svc.session.request = Mock(side_effect=RuntimeError("x"))
        assert svc.test_connection()["status"] == "error"

    def test_board_list_card_crud(self):
        svc = self.make()
        svc.session.request = Mock(return_value=_http_resp(200, [{"id": "1"}]))
        assert svc.get_boards() == [{"id": "1"}]
        assert svc.get_board("b1", fields=["name"]) == [{"id": "1"}]
        assert svc.get_board("b1") == [{"id": "1"}]
        assert svc.create_board("B") == [{"id": "1"}]
        assert svc.get_lists("b1", filter="all") == [{"id": "1"}]
        assert svc.create_list("b1", "L") == [{"id": "1"}]
        assert svc.get_cards(list_id="l1") == [{"id": "1"}]
        assert svc.get_cards(board_id="b1") == [{"id": "1"}]
        assert svc.get_cards() == [{"id": "1"}]
        assert svc.get_card("c1") == [{"id": "1"}]
        assert svc.create_card("C", "l1", description="d", due="2026-01-01",
                               labels=["x"], members=["m"]) == [{"id": "1"}]
        assert svc.create_card("C", "l1") == [{"id": "1"}]
        assert svc.update_card("c1", {"name": "x"}) == [{"id": "1"}]
        assert svc.archive_card("c1") is True
        assert svc.delete_card("c1") is True
        assert svc.add_comment("c1", "hi") == [{"id": "1"}]
        assert svc.get_comments("c1") == [{"id": "1"}]
        assert svc.get_checklists("c1") == [{"id": "1"}]
        assert svc.create_checklist("c1", "CL") == [{"id": "1"}]
        assert svc.add_checklist_item("cl1", "item") == [{"id": "1"}]
        assert svc.move_card("c1", "l2") == [{"id": "1"}]
        assert svc.get_members("b1") == [{"id": "1"}]
        assert svc.add_member_to_card("c1", "m1") == [{"id": "1"}]
        assert svc.remove_member_from_card("c1", "m1") is True
        assert svc.get_labels("b1") == [{"id": "1"}]
        assert svc.create_label("b1", "urgent", color="red") == [{"id": "1"}]
        assert svc.create_label("b1", "urgent") == [{"id": "1"}]
        assert svc.add_label_to_card("c1", "l1") == [{"id": "1"}]
        assert svc.remove_label_from_card("c1", "l1") is True
        assert svc.get_user_profile() == [{"id": "1"}]
        assert svc.search("q", board_id="b1") == []
        assert svc.get_activities("b1", since="2026-01-01") == [{"id": "1"}]
        assert svc.get_activities("b1") == [{"id": "1"}]

    def test_error_paths(self):
        svc = self.make()
        svc.session.request = Mock(side_effect=RuntimeError("x"))
        assert svc.get_boards() == []
        assert svc.get_board("b") is None
        assert svc.create_board("B") is None
        assert svc.get_lists("b") == []
        assert svc.create_list("b", "L") is None
        assert svc.get_cards() == []
        assert svc.get_card("c") is None
        assert svc.create_card("C", "l") is None
        assert svc.update_card("c", {}) is None
        assert svc.archive_card("c") is False
        assert svc.delete_card("c") is False
        assert svc.add_comment("c", "x") is None
        assert svc.get_comments("c") == []
        assert svc.get_checklists("c") == []
        assert svc.create_checklist("c", "n") is None
        assert svc.add_checklist_item("cl", "n") is None
        assert svc.get_members("b") == []
        assert svc.add_member_to_card("c", "m") is None
        assert svc.remove_member_from_card("c", "m") is False
        assert svc.get_labels("b") == []
        assert svc.create_label("b", "n") is None
        assert svc.add_label_to_card("c", "l") is None
        assert svc.remove_label_from_card("c", "l") is False
        assert svc.get_user_profile() is None
        assert svc.search("q") == []
        assert svc.get_activities("b") == []

    def test_sync_and_full_sync(self):
        svc = self.make()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_boards", return_value=[{}, {}]):
            r = svc.sync_to_postgres_cache("ws-1")
        assert r["success"] is True and r["metrics_synced"] == 1

        db2 = MagicMock()
        db2.query.side_effect = RuntimeError("db down")
        with patch("core.database.SessionLocal", return_value=db2), \
             patch.object(svc, "get_boards", return_value=[]):
            r = svc.sync_to_postgres_cache("ws-1")
        assert not r["success"]

        with patch.object(svc, "sync_to_postgres_cache", return_value={"success": True}):
            r = svc.full_sync("ws-1")
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_service_info_health_capabilities(self):
        svc = self.make()
        info = await svc.get_service_info()
        assert info["status"] == "operational"
        with patch.object(svc, "test_connection", return_value={"status": "success", "message": "ok"}):
            assert svc.health_check()["healthy"] is True
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is True

    @pytest.mark.asyncio
    async def test_execute_operation_and_ops(self):
        svc = self.make()
        with patch.object(svc, "create_card", return_value={"id": "1"}), \
             patch.object(svc, "get_cards", return_value=[]), \
             patch.object(svc, "update_card", return_value={"id": "1"}), \
             patch.object(svc, "get_boards", return_value=[]), \
             patch.object(svc, "add_comment", return_value={"id": 1}):
            assert (await svc.execute_operation("create_card", {"name": "C", "list_id": "l"}))["success"]
            assert (await svc.execute_operation("get_cards", {}))["success"]
            assert (await svc.execute_operation("update_card", {"card_id": "c"}) )["success"]
            assert (await svc.execute_operation("get_boards", {}))["success"]
            assert (await svc.execute_operation("add_comment", {}))["success"]
            r = await svc.execute_operation("bogus", {})
            assert not r["success"]
            r = await svc.execute_operation("create_card", {}, context={"tenant_id": "other"})
            assert not r["success"]
        with patch.object(svc, "create_card", return_value=None):
            r = await svc.execute_operation("create_card", {"name": "C", "list_id": "l"})
            assert not r["success"]
        with patch.object(svc, "update_card", return_value=None):
            r = await svc.execute_operation("update_card", {"card_id": "c"})
            assert not r["success"]
        with patch.object(svc, "add_comment", return_value=None):
            r = await svc.execute_operation("add_comment", {})
            assert not r["success"]
        with patch.object(svc, "create_card", side_effect=RuntimeError("x")):
            r = await svc.execute_operation("create_card", {})
            assert not r["success"]


# ============================================================================
# hubspot_routes.py - HubSpotService class internals
# ============================================================================

class TestHubspotRoutesServiceClass:
    @pytest.mark.asyncio
    async def test_service_authenticate_and_hub_id(self):
        import integrations.hubspot_routes as routes

        svc = routes.HubSpotService()
        svc.client.post = AsyncMock(return_value=_http_resp(
            200, {"access_token": "at", "refresh_token": "rt", "expires_in": 3600}))
        svc.client.get = AsyncMock(return_value=_http_resp(200, {"portalId": "42"}))
        req = routes.HubSpotAuthRequest(client_id="c", client_secret="s",
                                        redirect_uri="http://x", code="code")
        r = await svc.authenticate(req)
        assert r["access_token"] == "at" and r["hub_id"] == "42"

        import httpx
        from fastapi import HTTPException
        svc.client.post = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.authenticate(req)
        svc.client.post = AsyncMock(side_effect=RuntimeError("y"))
        with pytest.raises(HTTPException):
            await svc.authenticate(req)

    @pytest.mark.asyncio
    async def test_get_hub_id_failure(self):
        import integrations.hubspot_routes as routes

        svc = routes.HubSpotService()
        svc.access_token = "t"
        svc.client.get = AsyncMock(side_effect=RuntimeError("x"))
        await svc._get_hub_id()
        assert svc.hub_id is None

    @pytest.mark.asyncio
    async def test_get_contacts_companies_deals_campaigns_lists(self):
        import integrations.hubspot_routes as routes

        now_ms = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        svc = routes.HubSpotService()
        svc.access_token = "t"
        svc.client.get = AsyncMock(return_value=_http_resp(200, {
            "results": [{
                "id": "1",
                "properties": {"email": "a@b.c", "createdate": str(now_ms),
                               "lastmodifieddate": str(now_ms)},
            }],
            "campaigns": [{"id": "c1", "name": "C", "createdAt": str(now_ms),
                           "updatedAt": str(now_ms)}],
            "lists": [{"listId": "l1", "name": "L", "createdAt": str(now_ms)}],
        }))
        contacts = await svc.get_contacts(limit=5, offset=1)
        assert contacts[0].email == "a@b.c"
        companies = await svc.get_companies(limit=5, offset=1)
        assert len(companies) == 1
        deals = await svc.get_deals(limit=5, offset=1)
        assert len(deals) == 1
        campaigns = await svc.get_campaigns(limit=5, offset=1)
        assert campaigns[0].name == "C"
        lists = await svc.get_lists(limit=5, offset=1)
        assert lists[0].name == "L"

        from fastapi import HTTPException
        import httpx
        svc2 = routes.HubSpotService()
        svc2.access_token = None
        with pytest.raises(HTTPException):
            await svc2.get_contacts()
        with pytest.raises(HTTPException):
            await svc2.get_companies()
        with pytest.raises(HTTPException):
            await svc2.get_deals()
        with pytest.raises(HTTPException):
            await svc2.get_campaigns()
        with pytest.raises(HTTPException):
            await svc2.get_lists()
        svc.client.get = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.get_contacts()
        with pytest.raises(HTTPException):
            await svc.get_companies()
        with pytest.raises(HTTPException):
            await svc.get_deals()
        with pytest.raises(HTTPException):
            await svc.get_campaigns()
        with pytest.raises(HTTPException):
            await svc.get_lists()
        svc.client.get = AsyncMock(side_effect=RuntimeError("y"))
        with pytest.raises(HTTPException):
            await svc.get_contacts()
        with pytest.raises(HTTPException):
            await svc.get_companies()
        with pytest.raises(HTTPException):
            await svc.get_deals()
        with pytest.raises(HTTPException):
            await svc.get_campaigns()
        with pytest.raises(HTTPException):
            await svc.get_lists()

    @pytest.mark.asyncio
    async def test_deal_parsing_with_amount_and_close_date(self):
        import integrations.hubspot_routes as routes

        now_ms = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        svc = routes.HubSpotService()
        svc.access_token = "t"
        svc.client.get = AsyncMock(return_value=_http_resp(200, {
            "results": [{
                "id": "d1",
                "properties": {"dealname": "D", "amount": "1000",
                               "dealstage": "x", "pipeline": "p",
                               "closedate": str(now_ms),
                               "createdate": str(now_ms), "lastmodifieddate": str(now_ms),
                               "hubspot_owner_id": "o1"},
            }]
        }))
        deals = await svc.get_deals()
        assert deals[0].amount == 1000.0
        assert deals[0].close_date is not None
        assert deals[0].owner_id == "o1"

    @pytest.mark.asyncio
    async def test_get_contacts_wrapper_and_deals_wrapper(self):
        import integrations.hubspot_routes as routes
        from fastapi import HTTPException

        svc = routes.HubSpotService()
        svc.access_token = None
        with pytest.raises(HTTPException):
            await svc.get_contacts_wrapper()
        with pytest.raises(HTTPException):
            await svc.get_deals_wrapper()
        svc.access_token = "t"
        with patch.object(svc, "get_contacts", new=AsyncMock(return_value=[])):
            assert await svc.get_contacts_wrapper(10, 0) == []
        with patch.object(svc, "get_deals", new=AsyncMock(return_value=[])):
            assert await svc.get_deals_wrapper(10, 0) == []

    @pytest.mark.asyncio
    async def test_search_content_create_contact_create_deal(self):
        import integrations.hubspot_routes as routes
        from fastapi import HTTPException
        import httpx

        svc = routes.HubSpotService()
        svc.access_token = "t"
        svc.client.post = AsyncMock(return_value=_http_resp(200, {"results": [], "total": 0}))
        req = routes.HubSpotSearchRequest(query="q", object_type="contact")
        r = await svc.search_content(req)
        assert r.total == 0

        c = routes.HubSpotContactCreate(email="a@b.c", first_name="A")
        svc.client.post = AsyncMock(return_value=_http_resp(201, {"id": "1"}))
        assert (await svc.create_contact(c))["id"] == "1"

        from datetime import datetime
        d = routes.HubSpotDealCreate(deal_name="D", amount=10.0, stage="x", pipeline="p",
                                     close_date=datetime(2026, 1, 1))
        assert (await svc.create_deal(d))["id"] == "1"
        d2 = routes.HubSpotDealCreate(deal_name="D", stage="x", pipeline="p")
        assert (await svc.create_deal(d2))["id"] == "1"

        svc2 = routes.HubSpotService()
        svc2.access_token = None
        with pytest.raises(HTTPException):
            await svc2.search_content(req)
        with pytest.raises(HTTPException):
            await svc2.create_contact(c)
        with pytest.raises(HTTPException):
            await svc2.create_deal(d)
        svc.client.post = AsyncMock(side_effect=httpx.HTTPError("x"))
        with pytest.raises(HTTPException):
            await svc.search_content(req)
        with pytest.raises(HTTPException):
            await svc.create_contact(c)
        with pytest.raises(HTTPException):
            await svc.create_deal(d)
        svc.client.post = AsyncMock(side_effect=RuntimeError("y"))
        with pytest.raises(HTTPException):
            await svc.search_content(req)
        with pytest.raises(HTTPException):
            await svc.create_contact(c)
        with pytest.raises(HTTPException):
            await svc.create_deal(d)

    @pytest.mark.asyncio
    async def test_get_stats_health_wrappers(self):
        import integrations.hubspot_routes as routes

        svc = routes.HubSpotService()
        svc.access_token = "t"
        adv = MagicMock()
        adv.analytics_metrics = {"total_contacts": 1, "total_companies": 2, "total_deals": 3,
                                 "total_campaigns": 4, "active_deals": 5, "won_deals": 6,
                                 "lost_deals": 7, "total_revenue": 8.0}
        svc.advanced_service = adv
        stats = await svc.get_stats()
        assert stats.total_contacts == 1
        svc.advanced_service = None
        stats = await svc.get_stats()
        assert stats.total_contacts == 1500
        svc.access_token = None
        with pytest.raises(Exception):
            await svc.get_stats()

        r = await svc.health_check()
        assert r["ok"] is True
        with patch("integrations.hubspot_routes.get_mock_mode_manager") as mm:
            mgr = MagicMock()
            mgr.is_mock_mode.return_value = True
            mm.return_value = mgr
            r = await svc.health_check_wrapper()
            assert r["is_mock"] is True
            mgr.is_mock_mode.return_value = False
            r = await svc.health_check_wrapper()
            assert r["ok"] is True


# ============================================================================
# freshdesk_service.py
# ============================================================================

class TestFreshdeskService:
    def make(self, config=None):
        import integrations.freshdesk_service as fd

        return fd.FreshdeskService(config=config or {
            "freshdesk_api_key": "k", "freshdesk_domain": "acme"})

    def test_init_without_domain(self):
        import integrations.freshdesk_service as fd

        s = fd.FreshdeskService(config={})
        assert s.base_url == ""
        assert s.headers["Authorization"] == ""
        assert s.api_key is None

    def test_capabilities_and_encoding(self):
        svc = self.make()
        caps = svc.get_capabilities()
        assert caps["supports_webhooks"] is True
        assert svc._encode_credentials() != ""

    @pytest.mark.asyncio
    async def test_execute_operation(self):
        svc = self.make()
        with patch.object(svc, "get_tickets", new=AsyncMock(return_value=[{}])), \
             patch.object(svc, "create_ticket", new=AsyncMock(return_value={"id": 1})), \
             patch.object(svc, "search_tickets", new=AsyncMock(return_value=[{}])):
            r = await svc.execute_operation("get_tickets", {"page": 2})
            assert r["success"] is True
            r = await svc.execute_operation("create_ticket", {"data": {"subject": "x"}})
            assert r["success"] is True
            r = await svc.execute_operation("search_tickets", {"query": "q"})
            assert r["success"] is True
            r = await svc.execute_operation("bogus", {})
            assert not r["success"]
            r = await svc.execute_operation("get_tickets", {}, context={"tenant_id": "other"})
            assert not r["success"]
        with patch.object(svc, "get_tickets", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc.execute_operation("get_tickets", {})
            assert not r["success"]

    @pytest.mark.asyncio
    async def test_handle_request_retries(self):
        import httpx
        import integrations.freshdesk_service as fd

        svc = self.make()
        import asyncio

        # success on first try
        resp = _http_resp(200, {"ok": 1})
        assert await svc._handle_request(AsyncMock(return_value=resp)) == {"ok": 1}

        # HTTPStatusError twice then success
        err_resp = MagicMock()
        err_resp.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
            "bad", request=Mock(), response=err_resp))
        ok_resp = _http_resp(200, {"ok": 2})
        calls = [err_resp, ok_resp]
        svc2 = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                           "freshdesk_domain": "acme",
                                           "freshdesk_max_retries": 3})
        with patch("integrations.freshdesk_service.httpx.AsyncClient") as ac:
            ac.return_value.aclose = AsyncMock()
            out = await svc2._handle_request(AsyncMock(side_effect=calls))
        assert out == {"ok": 2}

        # exhausted retries -> raise
        svc3 = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                           "freshdesk_domain": "acme",
                                           "freshdesk_max_retries": 2})
        with patch("integrations.freshdesk_service.httpx.AsyncClient") as ac:
            ac.return_value.aclose = AsyncMock()
            with pytest.raises(httpx.HTTPStatusError):
                await svc3._handle_request(AsyncMock(return_value=err_resp))

        # RequestError retry
        err2 = httpx.RequestError("net", request=Mock())
        with patch("integrations.freshdesk_service.httpx.AsyncClient") as ac:
            ac.return_value.aclose = AsyncMock()
            with pytest.raises(httpx.RequestError):
                await svc3._handle_request(AsyncMock(side_effect=err2))

    @pytest.mark.asyncio
    async def test_ticket_methods(self):
        svc = self.make()
        with patch.object(svc, "_handle_request", new=AsyncMock(return_value={"id": 1})):
            assert (await svc.create_ticket({"subject": "x"}))["id"] == 1
            assert (await svc.get_tickets(status="open", priority="1", created_since="2026-01-01"))["id"] == 1
            assert (await svc.get_tickets())["id"] == 1
            assert (await svc.get_ticket(1))["id"] == 1
            assert (await svc.update_ticket(1, {"status": 4}))["id"] == 1
            assert await svc.delete_ticket(1) is True
            assert (await svc.add_ticket_note(1, {"body": "n"}))["id"] == 1
            assert (await svc.get_ticket_conversations(1))["id"] == 1
        with patch.object(svc, "_handle_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            with pytest.raises(RuntimeError):
                await svc.create_ticket({"subject": "x"})
            with pytest.raises(RuntimeError):
                await svc.get_tickets()
            with pytest.raises(RuntimeError):
                await svc.get_ticket(1)
            with pytest.raises(RuntimeError):
                await svc.update_ticket(1, {})
            with pytest.raises(RuntimeError):
                await svc.delete_ticket(1)
            with pytest.raises(RuntimeError):
                await svc.add_ticket_note(1, {})
            with pytest.raises(RuntimeError):
                await svc.get_ticket_conversations(1)

    @pytest.mark.asyncio
    async def test_contact_company_agent_group_methods(self):
        svc = self.make()
        with patch.object(svc, "_handle_request", new=AsyncMock(return_value={"id": 1})):
            assert (await svc.create_contact({}))["id"] == 1
            assert (await svc.get_contacts(page=2, per_page=10))["id"] == 1
            assert (await svc.get_contact(1))["id"] == 1
            assert (await svc.update_contact(1, {}))["id"] == 1
            assert (await svc.create_company({}))["id"] == 1
            assert (await svc.get_companies(page=1, per_page=5))["id"] == 1
            assert (await svc.get_company(1))["id"] == 1
            assert (await svc.get_agents())["id"] == 1
            assert (await svc.get_agent(1))["id"] == 1
            assert (await svc.get_groups())["id"] == 1
            assert (await svc.get_group(1))["id"] == 1

    @pytest.mark.asyncio
    async def test_analytics_search_account_upload(self):
        svc = self.make()
        with patch.object(svc, "_handle_request", new=AsyncMock(return_value={"r": 1})):
            assert (await svc.get_tickets_metrics(date_range="30d", group_by="agent")) == {"r": 1}
            assert (await svc.get_tickets_metrics()) == {"r": 1}
            assert (await svc.get_satisfaction_ratings(ticket_id=1, date_range="7d")) == {"r": 1}
            assert (await svc.get_satisfaction_ratings()) == {"r": 1}
            assert (await svc.search_tickets("q", {"status": 2})) == {"r": 1}
            assert (await svc.search_tickets("q")) == {"r": 1}
            assert (await svc.search_contacts("q")) == {"r": 1}
            assert (await svc.get_account_info()) == {"r": 1}
        with patch.object(svc, "_handle_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            with pytest.raises(RuntimeError):
                await svc.get_tickets_metrics()
            with pytest.raises(RuntimeError):
                await svc.get_satisfaction_ratings()
            with pytest.raises(RuntimeError):
                await svc.search_tickets("q")
            with pytest.raises(RuntimeError):
                await svc.search_contacts("q")
            with pytest.raises(RuntimeError):
                await svc.get_account_info()
            with pytest.raises(RuntimeError):
                await svc.upload_attachment(b"data", "f.txt")

    @pytest.mark.asyncio
    async def test_health_check_and_utils(self):
        svc = self.make()
        with patch("requests.get") as rg:
            rg.return_value.status_code = 200
            rg.return_value.text = "ok"
            r = svc.health_check()
            assert r["healthy"] is True
            rg.return_value.status_code = 500
            r = svc.health_check()
            assert r["healthy"] is False and r["api_response"] is None
            rg.side_effect = RuntimeError("x")
            r = svc.health_check()
            assert r["healthy"] is False
        s2 = self.make.__self__
        import integrations.freshdesk_service as fd
        bare = fd.FreshdeskService(config={})
        r = bare.health_check()
        assert r["healthy"] is False and "Missing" in r["message"]

        assert svc.get_status_name(2) == "Open"
        assert svc.get_status_name(99) == "Unknown"
        assert svc.get_priority_name(1) == "Low"
        assert svc.get_priority_name(99) == "Unknown"
        await svc.close()

    @pytest.mark.asyncio
    async def test_factory_and_connection_test(self):
        import integrations.freshdesk_service as fd

        svc = fd.create_freshdesk_service("k", "acme", freshdesk_timeout=5)
        assert svc.domain == "acme"
        with patch.object(svc, "health_check", return_value={"healthy": True}):
            assert await fd.test_freshdesk_connection("k", "acme") is True
        with patch.object(fd.FreshdeskService, "health_check", side_effect=RuntimeError("x")):
            assert await fd.test_freshdesk_connection("k", "acme") is False
        assert fd.FreshdeskConstants.STATUS_OPEN == 2
        assert fd.DEFAULT_FRESHDESK_CONFIG["api_version"] == "v2"
        assert "FreshdeskService" in fd.__all__


# ============================================================================
# salesforce_routes.py
# ============================================================================

class TestSalesforceRoutes:
    @pytest.mark.asyncio
    async def test_access_token_dependency(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        with patch.object(routes.salesforce_auth_handler, "ensure_valid_token",
                          new=AsyncMock(return_value="tok")):
            assert await routes.get_salesforce_access_token() == "tok"
        with patch.object(routes.salesforce_auth_handler, "ensure_valid_token",
                          new=AsyncMock(side_effect=HTTPException(status_code=401))):
            with pytest.raises(HTTPException):
                await routes.get_salesforce_access_token()

    def test_get_client_from_env(self):
        import integrations.salesforce_routes as routes

        with patch.object(routes.salesforce_auth_handler, "is_token_valid", return_value=True), \
             patch.object(routes.salesforce_auth_handler, "instance_url", "https://x.salesforce.com"), \
             patch.object(routes.salesforce_auth_handler, "access_token", "tok"):
            client = routes.get_salesforce_client_from_env()
        assert client is not None

        with patch.object(routes.salesforce_auth_handler, "is_token_valid", return_value=False), \
             patch.dict("os.environ", {"SALESFORCE_USERNAME": "u", "SALESFORCE_PASSWORD": "p",
                                       "SALESFORCE_SECURITY_TOKEN": "t"}, clear=False), \
             patch.object(routes, "Salesforce", return_value=Mock()):
            client = routes.get_salesforce_client_from_env()
        assert client is not None

        with patch.object(routes.salesforce_auth_handler, "is_token_valid", return_value=False), \
             patch.dict("os.environ", {}, clear=False), \
             patch.object(routes, "Salesforce", side_effect=RuntimeError("x")):
            assert routes.get_salesforce_client_from_env() is None

    @pytest.mark.asyncio
    async def test_oauth_endpoints(self):
        import integrations.salesforce_routes as routes

        with patch.object(routes.salesforce_auth_handler, "get_authorization_url",
                          return_value="https://auth"):
            r = await routes.get_salesforce_auth_url()
        assert r["url"] == "https://auth"

        with patch.object(routes.salesforce_auth_handler, "exchange_code_for_token",
                          new=AsyncMock(return_value={"instance_url": "https://x"})):
            r = await routes.salesforce_auth_callback("code", state="s")
        assert r["ok"] is True
        from fastapi import HTTPException
        with patch.object(routes.salesforce_auth_handler, "exchange_code_for_token",
                          new=AsyncMock(side_effect=HTTPException(status_code=400))):
            with pytest.raises(HTTPException):
                await routes.salesforce_auth_callback("code")
        with patch.object(routes.salesforce_auth_handler, "exchange_code_for_token",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            with pytest.raises(HTTPException) as ei:
                await routes.salesforce_auth_callback("code")
        assert ei.value.status_code == 500

        with patch.object(routes.salesforce_auth_handler, "revoke_token",
                          new=AsyncMock(return_value=True)):
            assert (await routes.revoke_salesforce_token())["ok"] is True
        with patch.object(routes.salesforce_auth_handler, "revoke_token",
                          new=AsyncMock(return_value=False)):
            assert (await routes.revoke_salesforce_token())["ok"] is False

        with patch.object(routes.salesforce_auth_handler, "get_connection_status",
                          return_value="connected"):
            assert (await routes.get_salesforce_status())["status"] == "connected"

    def test_format_helpers(self):
        import integrations.salesforce_routes as routes

        r = routes.format_salesforce_response({"a": 1})
        assert r["ok"] is True and r["data"] == {"a": 1}
        e = routes.format_salesforce_error_response("boom")
        assert e["ok"] is False and e["error"]["code"] == "SALESFORCE_ERROR"

    @pytest.mark.asyncio
    async def test_health_check(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        with patch.object(routes, "SALESFORCE_AVAILABLE", False):
            with pytest.raises(HTTPException) as ei:
                await routes.salesforce_health_check()
            assert ei.value.status_code == 503

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.salesforce_health_check()
        assert r["connected"] is False

        sf = Mock()
        sf.query = Mock()
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.salesforce_health_check()
        assert r["connected"] is True
        sf.query = Mock(side_effect=RuntimeError("x"))
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.salesforce_health_check()
        assert r["connected"] is False

    @pytest.mark.asyncio
    async def test_accounts_routes(self):
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", False):
            from fastapi import HTTPException
            with pytest.raises(HTTPException):
                await routes.get_salesforce_accounts(limit=10, access_token="t")

        sf = Mock()
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_accounts", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record"):
            r = await routes.get_salesforce_accounts(limit=10, access_token="t")
        assert r["ok"] is True and r["data"]["accounts"][0]["Id"] == "1"

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_salesforce_accounts(limit=10, access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_accounts", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.get_salesforce_accounts(limit=10, access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch("integrations.salesforce_service.validate_salesforce_id",
                   return_value=False):
            r = await routes.get_salesforce_account("001xx", access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_salesforce_account("001xx", access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch("integrations.salesforce_service.validate_salesforce_id",
                   return_value=True), \
             patch("integrations.salesforce_service.escape_soql_string",
                   return_value="001xx"), \
             patch.object(routes, "execute_soql_query", new=AsyncMock(
                 return_value={"records": [{"Id": "1"}]})):
            r = await routes.get_salesforce_account("001xx", access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch("integrations.salesforce_service.validate_salesforce_id",
                   return_value=True), \
             patch("integrations.salesforce_service.escape_soql_string",
                   return_value="001xx"), \
             patch.object(routes, "execute_soql_query", new=AsyncMock(
                 return_value={"records": []})):
            r = await routes.get_salesforce_account("001xx", access_token="t")
        assert r["ok"] is False

    @pytest.mark.asyncio
    async def test_create_account_governance_paths(self):
        import integrations.salesforce_routes as routes

        sf = Mock()
        base = {"name": "Acme", "access_token": "t"}
        # governance allowed
        gov = {"allowed": True, "reason": ""}
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "with_governance_check",
                          new=AsyncMock(return_value=(Mock(id="a1"), gov))), \
             patch.object(routes, "create_account", new=AsyncMock(return_value={"Id": "1"})), \
             patch.object(routes, "create_execution_record", return_value=Mock()):
            r = await routes.create_salesforce_account(agent_id="ag1", db=Mock(), **base)
        assert r["ok"] is True

        # governance blocked
        from fastapi import HTTPException
        gov = {"allowed": False, "reason": "nope"}
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "with_governance_check",
                          new=AsyncMock(return_value=(Mock(id="a1"), gov))):
            with pytest.raises(HTTPException) as ei:
                await routes.create_salesforce_account(agent_id="ag1", db=Mock(), **base)
        assert ei.value.status_code == 403

        # governance error -> logged, still proceeds
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))), \
             patch.object(routes, "create_account", new=AsyncMock(return_value={"Id": "1"})):
            r = await routes.create_salesforce_account(agent_id="ag1", db=Mock(), **base)
        assert r["ok"] is True

        # no creds + no agent_id
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.create_salesforce_account(db=Mock(), **base)
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_account",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.create_salesforce_account(db=Mock(), **base)
        assert r["ok"] is False

    @pytest.mark.asyncio
    async def test_contacts_routes(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        sf = Mock()
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_contacts", new=AsyncMock(return_value=[
                 {"Id": "1", "AccountId": "acc1", "Email": "a@b.c"},
                 {"Id": "2", "AccountId": "acc2", "Email": "x@y.z"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record"):
            r = await routes.get_salesforce_contacts(limit=10, access_token="t",
                                                     account_id="acc1", email="a@b.c")
        assert r["ok"] is True and len(r["data"]) == 1
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_salesforce_contacts(limit=10, access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_contacts", new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.get_salesforce_contacts(limit=10, access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_contact", new=AsyncMock(return_value={"Id": "1"})):
            r = await routes.create_salesforce_contact(first_name="A", last_name="B",
                                                       email="a@b.c", access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.create_salesforce_contact(first_name="A", last_name="B",
                                                       email="a@b.c", access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_contact",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.create_salesforce_contact(first_name="A", last_name="B",
                                                       email="a@b.c", access_token="t")
        assert r["ok"] is False

    @pytest.mark.asyncio
    async def test_opportunity_lead_routes(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        sf = Mock()
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_opportunities", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record"):
            r = await routes.get_salesforce_opportunities(limit=10, access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_salesforce_opportunities(limit=10, access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_opportunities",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.get_salesforce_opportunities(limit=10, access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_opportunity", new=AsyncMock(return_value={"Id": "1"})):
            r = await routes.create_salesforce_opportunity(
                name="Opp", account_id="a1", stage="Prospecting", amount=100.0,
                close_date="2026-01-01", access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.create_salesforce_opportunity(
                name="Opp", account_id="a1", stage="Prospecting", amount=100.0,
                close_date="2026-01-01", access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_opportunity",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.create_salesforce_opportunity(
                name="Opp", account_id="a1", stage="Prospecting", amount=100.0,
                close_date="2026-01-01", access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_leads", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record"):
            r = await routes.get_salesforce_leads(limit=10, access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_lead", new=AsyncMock(return_value={"Id": "1"})):
            r = await routes.create_salesforce_lead(first_name="A", last_name="B",
                                                    company="C", email="a@b.c", access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "create_lead",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.create_salesforce_lead(first_name="A", last_name="B",
                                                    company="C", email="a@b.c", access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.create_salesforce_lead(first_name="A", last_name="B",
                                                    company="C", email="a@b.c", access_token="t")
        assert r["ok"] is False

    @pytest.mark.asyncio
    async def test_search_analytics_profile_stripe_routes(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        sf = Mock()
        sf.search = Mock(return_value={"searchRecords": []})
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.search_salesforce(query="q", object_types=["Account"],
                                               access_token="t")
        assert r["ok"] is True
        sf.search = Mock(side_effect=RuntimeError("x"))
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.search_salesforce(query="q", object_types=["Account"],
                                               access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.search_salesforce(query="q", object_types=["Account"],
                                               access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", side_effect=RuntimeError("x")):
            r = await routes.search_salesforce(query="q", object_types=["Account"],
                                               access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "execute_soql_query", new=AsyncMock(
                 return_value={"records": [{"Amount": "10.5"}, {"Amount": None}]})):
            r = await routes.get_sales_pipeline_analytics(access_token="t")
        assert r["ok"] is True and r["data"]["pipeline_value"] == 10.5
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_sales_pipeline_analytics(access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "execute_soql_query",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await routes.get_sales_pipeline_analytics(access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "execute_soql_query", new=AsyncMock(
                 return_value={"records": [{"IsConverted": True}, {"IsConverted": False},
                                           {"IsConverted": True}]})):
            r = await routes.get_leads_analytics(access_token="t")
        assert r["ok"] is True and r["data"]["converted_count"] == 2
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "execute_soql_query",
                          new=AsyncMock(return_value={"records": []})):
            r = await routes.get_leads_analytics(access_token="t")
        assert r["ok"] is True and r["data"]["conversion_rate"] == 0.0

        sf.restful = Mock(return_value={"username": "bob"})
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.get_salesforce_user_profile(access_token="t")
        assert r["ok"] is True and r["data"]["username"] == "bob"
        sf.restful = Mock(side_effect=RuntimeError("x"))
        sf.query = Mock(return_value={"totalSize": 1, "records": [{"Id": "1"}]})
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.get_salesforce_user_profile(access_token="t")
        assert r["ok"] is True
        sf.query = Mock(return_value={"totalSize": 0})
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.get_salesforce_user_profile(access_token="t")
        assert r["ok"] is False
        sf.query = Mock(side_effect=RuntimeError("db"))
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf):
            r = await routes.get_salesforce_user_profile(access_token="t")
        assert r["ok"] is False
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=None):
            r = await routes.get_salesforce_user_profile(access_token="t")
        assert r["ok"] is False

        with patch.object(routes, "SALESFORCE_AVAILABLE", True):
            r = await routes.sync_stripe_payments_with_salesforce(
                {"id": "p1", "amount": 100}, opportunity_id="o1", access_token="t")
        assert r["ok"] is True and r["data"]["payment_id"] == "p1"

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "format_salesforce_response",
                          side_effect=RuntimeError("x")):
            r = await routes.sync_stripe_payments_with_salesforce(
                {"id": "p1"}, access_token="t")
        assert r["ok"] is False

        r = await routes.salesforce_root()
        assert r["service"] == "salesforce"


# ============================================================================
# atom_hubspot_integration_service.py - deep branch coverage
# ============================================================================

_FAKE_AI_MODULES = {
    "ai_enhanced_service": {
        "AIModelType": type("_E", (), {"GPT_4": "gpt-4"}),
        "AIRequest": lambda **kw: kw,
        "AIResponse": None,
        "AIServiceType": type("_E", (), {"OPENAI": "openai"}),
        "AITaskType": type("_E", (), {"PREDICTION": "prediction", "CONTENT_ANALYSIS": "content"}),
        "ai_enhanced_service": MagicMock(),
    },
    "atom_ai_integration": {"atom_ai_integration": MagicMock()},
    "atom_discord_integration": {"atom_discord_integration": MagicMock()},
    "atom_enterprise_security_service": {
        "ComplianceStandard": type("_E", (), {"SOC2": "soc2"}),
        "SecurityLevel": type("_E", (), {"HIGH": "high"}),
        "atom_enterprise_security_service": MagicMock(),
    },
    "atom_google_chat_integration": {"atom_google_chat_integration": MagicMock()},
    "atom_slack_integration": {"atom_slack_integration": MagicMock()},
    "atom_teams_integration": {"atom_teams_integration": MagicMock()},
    "atom_telegram_integration": {"atom_telegram_integration": MagicMock()},
    "atom_whatsapp_integration": {"atom_whatsapp_integration": MagicMock()},
    "atom_workflow_automation_service": {
        "AutomationPriority": type("_E", (), {"HIGH": "high"}),
        "AutomationStatus": type("_E", (), {"ACTIVE": "active"}),
        "atom_workflow_automation_service": MagicMock(),
    },
    "atom_zoom_integration": {"atom_zoom_integration": MagicMock()},
}


@pytest.fixture
def hubspot_with_enterprise():
    """Reload the hubspot integration module with fake enterprise services."""
    import importlib
    import sys
    import types

    import integrations.atom_hubspot_integration_service as mod

    saved = {}
    for name, attrs in _FAKE_AI_MODULES.items():
        saved[name] = sys.modules.get(name)
        fake = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(fake, k, v)
        sys.modules[name] = fake
    importlib.reload(mod)
    yield mod
    importlib.reload(mod)
    for name, orig in saved.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


class TestAtomHubspotDeep:
    @pytest.fixture(autouse=True)
    def _no_throttle(self):
        with patch("integrations.atom_hubspot_integration_service.rate_limiter") as rl, \
             patch("integrations.atom_hubspot_integration_service.circuit_breaker") as cb:
            rl.is_rate_limited = AsyncMock(return_value=(False, 1000))
            cb.is_enabled = AsyncMock(return_value=True)
            yield

    @pytest.mark.asyncio
    async def test_circuit_breaker_and_rate_limit_paths(self):
        from integrations.atom_hubspot_integration_service import (
            AnalyticsType,
            AtomHubSpotIntegrationService,
        )
        from fastapi import HTTPException

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        with patch("integrations.atom_hubspot_integration_service.circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=False)
            r = await svc.create_contact({"email": "a@b.c"})
            assert not r["success"] and "503" in r["error"]
            with pytest.raises(HTTPException) as ei:
                await svc.create_campaign({"name": "C"})
            assert ei.value.status_code == 503
            with pytest.raises(HTTPException) as ei:
                await svc.generate_marketing_analytics(AnalyticsType.LEAD_SCORING)
            assert ei.value.status_code == 503
            with pytest.raises(HTTPException) as ei:
                await svc.close()
            assert ei.value.status_code == 503

        with patch("integrations.atom_hubspot_integration_service.rate_limiter") as rl:
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc.create_contact({"email": "a@b.c"})
            assert not r["success"] and "429" in r["error"]
            with pytest.raises(HTTPException) as ei:
                await svc.create_campaign({"name": "C"})
            assert ei.value.status_code == 429
            with pytest.raises(HTTPException) as ei:
                await svc.generate_marketing_analytics(AnalyticsType.LEAD_SCORING)
            assert ei.value.status_code == 429
            with pytest.raises(HTTPException) as ei:
                await svc.close()
            assert ei.value.status_code == 429

    @pytest.mark.asyncio
    async def test_create_contact_security_fail_and_properties_merge(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={
            "hubspot_access_token": "t", "enable_enterprise_features": True,
            "security_service": MagicMock()})
        svc._perform_security_check = AsyncMock(return_value={
            "passed": False, "reason": "blocked"})
        r = await svc.create_contact({"email": "a@b.c"})
        assert not r["success"] and r["error"] == "blocked"

        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc2._perform_security_check = AsyncMock(return_value={"passed": True, "reason": ""})
        contact_resp = _http_resp(201, {"id": "1"})
        cm = _acm(post_result=contact_resp)
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc2.create_contact({"email": "a@b.c", "properties": {"x": 1}})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_create_contact_non_201_and_exception(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        cm = _acm(post_result=_http_resp(400, {}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_contact({"email": "a@b.c"})
        assert not r["success"] and "Failed to create contact" in r["error"]

        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("net down"))
        cm2 = MagicMock()
        cm2.__aenter__ = AsyncMock(return_value=client)
        cm2.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            r = await svc.create_contact({"email": "a@b.c"})
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_create_campaign_branches(self):
        from datetime import datetime
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc._perform_security_check = AsyncMock(return_value={
            "passed": False, "reason": "denied"})
        with patch.object(svc, "hubspot_config", {"enable_enterprise_features": True}):
            r = await svc.create_campaign({"name": "C"})
        assert not r["success"]

        svc2 = AtomHubSpotIntegrationService(config={
            "hubspot_access_token": "t", "enable_enterprise_features": True})
        svc2._perform_security_check = AsyncMock(return_value={"passed": True, "reason": ""})
        svc2._optimize_campaign_with_ai = AsyncMock(return_value={"predicted_performance": 1})
        cm = _acm(post_result=_http_resp(400, {}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc2.create_campaign({"name": "C", "start_date": datetime(2026, 1, 1)})
        assert not r["success"]

        svc3 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("net"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            r = await svc3.create_campaign({"name": "C", "start_date": datetime(2026, 1, 1)})
        assert not r["success"]

        svc4 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        r = await svc4.create_campaign({"name": "C"})  # missing start_date
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_create_campaign_platform_notification(self):
        from datetime import datetime
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations["slack"] = integration
        cm = _acm(post_result=_http_resp(201, {"id": "c9"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_campaign(
                {"name": "C", "start_date": datetime(2026, 1, 1)}, platform="slack")
        assert r["success"] is True
        integration.send_notification.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_marketing_analytics_all_types(self):
        from integrations.atom_hubspot_integration_service import (
            AnalyticsType,
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        for atype in AnalyticsType:
            with patch.object(svc, "_generate_campaign_performance_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_lead_conversion_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_email_performance_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_social_media_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_website_traffic_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_marketing_roi_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_lead_scoring_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_ab_testing_analytics",
                              new=AsyncMock(return_value={"insights": ["i"]})), \
                 patch.object(svc, "_generate_ai_insights",
                              new=AsyncMock(return_value={"note": "ai"})):
                r = await svc.generate_marketing_analytics(atype)
                assert r["success"] is True, atype
        r = await svc.generate_marketing_analytics("bogus")
        assert r["success"] is True
        assert r["analytics"]["metrics"]["error"] == "Unsupported analytics type"

    @pytest.mark.asyncio
    async def test_score_lead_with_ai_and_optimize_with_ai(self, hubspot_with_enterprise):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        ai = hubspot_with_enterprise
        ai_service = ai.ai_enhanced_service
        ai_service.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"lead_score": 85, "scoring_factors": {}}))
        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t",
                                                    "ai_service": ai_service})
        score = await svc._score_lead({"email": "x@y.com"})
        assert score == 85.0

        ai_service.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        score = await svc._score_lead({"email": "a@gmail.com"})
        assert 0 <= score <= 100

        ai_service.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"optimized_subject": "S"}))
        r = await svc._optimize_campaign_with_ai({"subject": "orig"})
        assert r["optimized_subject"] == "S"

        ai_service.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        r = await svc._optimize_campaign_with_ai({"subject": "orig"})
        assert r["optimized_subject"] == "orig"

        ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc._optimize_campaign_with_ai({"subject": "orig"})
        assert r["optimized_subject"] == "orig"
        score = await svc._score_lead({})
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_auth_headers_and_connection_test(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )
        import pytest as _pt

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        h = await svc._get_auth_headers()
        assert h["Authorization"] == "Bearer t"
        svc.hubspot_config["access_token"] = None
        svc.hubspot_config["api_key"] = "k"
        h = await svc._get_auth_headers()
        assert "Bearer k" in h["Authorization"]
        svc.hubspot_config["api_key"] = None
        with pytest.raises(Exception):
            await svc._get_auth_headers()

        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        cm = _acm(get_result=_http_resp(200, {}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            assert await svc2._test_hubspot_connection() is True
        cm2 = _acm(get_result=_http_resp(500, {}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            with pytest.raises(Exception):
                await svc2._test_hubspot_connection()
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("x"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            with pytest.raises(RuntimeError):
                await svc2._test_hubspot_connection()

    @pytest.mark.asyncio
    async def test_cache_and_workflow_methods(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        cache = MagicMock()
        cache.set = AsyncMock()
        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t",
                                                    "cache": cache})
        await svc._cache_contact({"id": "1"})
        await svc._cache_campaign({"id": "1"})
        cache.set.assert_awaited()
        await svc._trigger_automation_workflows({"id": "1"}, "contact_created")
        svc.automation_flows = {
            "f1": {"trigger_event": "contact_created",
                   "conditions": {"lead_score_min": 60},
                   "actions": [{"type": "send_email"}, {"type": "add_to_list"},
                               {"type": "create_task"}, {"type": "update_properties"}]},
            "f2": {"trigger_event": "other", "conditions": {}, "actions": []},
        }
        with patch.object(svc, "_execute_workflow", new=AsyncMock()) as ex:
            await svc._trigger_automation_workflows(
                {"properties": {"hs_lead_score": "70"}}, "contact_created")
            ex.assert_awaited_once()

        svc.hubspot_config["automation_workflows"] = False
        await svc._trigger_automation_workflows({"id": "1"}, "contact_created")

        await svc._trigger_campaign_workflows({"id": "c1", "status": "draft"}, "created")
        await svc._trigger_campaign_workflows({}, "created")

        assert svc._evaluate_workflow_conditions(
            {"lifecycle_stage": "lead"}, {"properties": {"lifecyclestage": "lead"}}) is True
        assert svc._evaluate_workflow_conditions(
            {"lifecycle_stage": "lead"}, {"properties": {"lifecyclestage": "customer"}}) is False
        assert svc._evaluate_workflow_conditions(
            {"lead_score_min": 50}, {"properties": {"hs_lead_score": "60"}}) is True
        assert svc._evaluate_workflow_conditions({}, {}) is True

        await svc._execute_workflow({"actions": []}, {"id": "1"})
        assert svc.performance_metrics["workflow_execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_workflow_action_helpers_and_notify(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        await svc._send_automated_email({"id": "1"}, {})
        await svc._add_contact_to_list({"id": "1"}, {"list_id": "l1"})
        await svc._create_marketing_task({"id": "1"}, {})
        await svc._update_contact_properties({"id": "1"}, {})

        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations["slack"] = integration
        await svc._notify_platform_lead_created({"id": "1"}, "slack")
        await svc._notify_platform_lead_created({"id": "1"}, "unknown_platform")
        await svc._notify_platform_campaign_created({"name": "C", "type": "x"}, "slack")
        await svc._notify_platform_campaign_created({}, "unknown")
        integration.send_notification.assert_awaited()

        cache_bad = MagicMock()
        cache_bad.set = AsyncMock(side_effect=RuntimeError("x"))
        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t",
                                                     "cache": cache_bad})
        await svc2._cache_contact({"id": "1"})
        await svc2._cache_campaign({"id": "1"})

    @pytest.mark.asyncio
    async def test_get_service_status_and_close(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        r = await svc.get_service_status()
        assert r["service"] == "hubspot_integration"
        svc.is_initialized = True
        r = await svc.get_service_status()
        assert r["status"] == "active"
        await svc.close()

        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc2.hubspot_config = {}
        r = await svc2.get_service_status()
        assert "error" in r

    @pytest.mark.asyncio
    async def test_security_check_and_setup_methods(self, hubspot_with_enterprise):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        assert (await svc._perform_security_check({}))["passed"] is True
        sec = MagicMock()
        sec.check = AsyncMock(return_value={"allowed": False, "reason": "no"})
        svc.enterprise_security = sec
        assert (await svc._perform_security_check({}))["passed"] is False
        sec.check = AsyncMock(return_value={"allowed": True})
        assert (await svc._perform_security_check({}))["passed"] is True
        sec.check = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc._perform_security_check({}))["passed"] is True

        await svc._setup_webhooks()
        await svc._setup_lead_scoring()
        await svc._setup_marketing_automation()
        await svc._setup_campaign_management()
        await svc._setup_real_time_tracking()
        await svc._setup_enterprise_features()
        await svc._setup_security_and_compliance()
        await svc._load_existing_data()
        await svc._start_monitoring()
        assert svc.webhook_handlers == {}


# ============================================================================
# atom_zendesk_integration_service.py - deep branch coverage
# ============================================================================

_FAKE_ZENDESK_MODULES = {
    "ai_enhanced_service": {
        "AIModelType": type("_E", (), {"GPT_4": "gpt-4"}),
        "AIRequest": lambda **kw: kw,
        "AIResponse": None,
        "AIServiceType": type("_E", (), {"OPENAI": "openai"}),
        "AITaskType": type("_E", (), {"PREDICTION": "prediction", "CONTENT_ANALYSIS": "content"}),
        "ai_enhanced_service": MagicMock(),
    },
    "atom_ai_integration": {"atom_ai_integration": MagicMock()},
    "atom_discord_integration": {"atom_discord_integration": MagicMock()},
    "atom_enterprise_security_service": {"atom_enterprise_security_service": MagicMock()},
    "atom_google_chat_integration": {"atom_google_chat_integration": MagicMock()},
    "atom_slack_integration": {"atom_slack_integration": MagicMock()},
    "atom_teams_integration": {"atom_teams_integration": MagicMock()},
    "atom_telegram_integration": {"atom_telegram_integration": MagicMock()},
    "atom_whatsapp_integration": {"atom_whatsapp_integration": MagicMock()},
    "atom_workflow_automation_service": {
        "AutomationPriority": type("_E", (), {"HIGH": "high"}),
        "AutomationStatus": type("_E", (), {"ACTIVE": "active"}),
        "atom_workflow_automation_service": MagicMock(),
    },
    "atom_zoom_integration": {"atom_zoom_integration": MagicMock()},
}


@pytest.fixture
def zendesk_with_enterprise():
    """Reload the zendesk integration module with fake enterprise services."""
    import importlib
    import sys
    import types

    import integrations.atom_zendesk_integration_service as mod

    saved = {}
    for name, attrs in _FAKE_ZENDESK_MODULES.items():
        saved[name] = sys.modules.get(name)
        fake = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(fake, k, v)
        sys.modules[name] = fake
    importlib.reload(mod)
    yield mod
    importlib.reload(mod)
    for name, orig in saved.items():
        if orig is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = orig


class TestAtomZendeskDeep:
    @pytest.fixture(autouse=True)
    def _no_throttle(self):
        with patch("integrations.atom_zendesk_integration_service.rate_limiter") as rl, \
             patch("integrations.atom_zendesk_integration_service.circuit_breaker") as cb:
            rl.is_rate_limited = AsyncMock(return_value=(False, 1000))
            cb.is_enabled = AsyncMock(return_value=True)
            yield

    @pytest.mark.asyncio
    async def test_initialize_success_and_failure(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        cm = _acm(get_result=_http_resp(200, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            assert await svc.initialize() is True
        assert svc.is_initialized is True

        svc2 = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        with patch.object(svc2, "_test_zendesk_connection",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc2.initialize() is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_and_rate_limit(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
            SupportAnalyticsType,
        )
        from fastapi import HTTPException

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        with patch("integrations.atom_zendesk_integration_service.circuit_breaker") as cb:
            cb.is_enabled = AsyncMock(return_value=False)
            r = await svc.create_ticket({"subject": "S"})
            assert not r["success"] and "503" in r["error"]
            r = await svc.update_ticket("1", {})
            assert not r["success"] and "503" in r["error"]
            with pytest.raises(HTTPException) as ei:
                await svc.get_ticket_info("1")
            assert ei.value.status_code == 503
            r = await svc.create_ticket_comment("1", "c")
            assert not r["success"] and "503" in r["error"]
            r = await svc.generate_support_analytics(SupportAnalyticsType.TICKET_VOLUME)
            assert not r["success"] and "503" in r["error"]
            await svc.close()

        with patch("integrations.atom_zendesk_integration_service.rate_limiter") as rl:
            rl.is_rate_limited = AsyncMock(return_value=(True, 0))
            r = await svc.create_ticket({"subject": "S"})
            assert not r["success"] and "429" in r["error"]
            r = await svc.update_ticket("1", {})
            assert not r["success"] and "429" in r["error"]
            with pytest.raises(HTTPException) as ei:
                await svc.get_ticket_info("1")
            assert ei.value.status_code == 429
            r = await svc.create_ticket_comment("1", "c")
            assert not r["success"] and "429" in r["error"]
            r = await svc.generate_support_analytics(SupportAnalyticsType.TICKET_VOLUME)
            assert not r["success"] and "429" in r["error"]

    @pytest.mark.asyncio
    async def test_create_ticket_security_assignee_notify_workflow(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t",
            "enable_enterprise_features": True,
            "security_service": MagicMock(),
            "enable_salesforce_integration": False,
        })
        svc._perform_security_check = AsyncMock(return_value={
            "passed": False, "reason": "blocked"})
        r = await svc.create_ticket({"subject": "S"})
        assert not r["success"] and r["error"] == "blocked"

        svc2 = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t",
            "enable_enterprise_features": True,
            "security_service": MagicMock(),
            "enable_salesforce_integration": False,
            "priority_auto_classification": False,
            "sentiment_analysis": False,
        })
        svc2._perform_security_check = AsyncMock(return_value={"passed": True, "reason": ""})
        svc2._auto_assign_ticket = AsyncMock(return_value="a1")
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc2.platform_integrations["slack"] = integration
        ticket_resp = _http_resp(201, {"ticket": {"id": "42"}})
        cm = _acm(post_result=ticket_resp)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc2.create_ticket({"subject": "S", "description": "D"},
                                         platform="slack")
        assert r["success"] is True and r["ticket_id"] == "42"
        integration.send_notification.assert_awaited()

    @pytest.mark.asyncio
    async def test_create_ticket_non_201_and_error(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False,
            "ticket_auto_assignment": False})
        cm = _acm(post_result=_http_resp(400, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_ticket({"subject": "S"})
        assert not r["success"] and "Failed to create ticket" in r["error"]

        client = MagicMock()
        client.post = AsyncMock(side_effect=RuntimeError("x"))
        cm2 = MagicMock()
        cm2.__aenter__ = AsyncMock(return_value=client)
        cm2.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            r = await svc.create_ticket({"subject": "S"})
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_update_ticket_branches(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False,
            "sla_monitoring": True, "escalation_rules": True})
        svc._get_ticket = AsyncMock(return_value=None)
        r = await svc.update_ticket("1", {"status": "solved"})
        assert not r["success"] and r["error"] == "Ticket not found"

        svc2 = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False,
            "sla_monitoring": True, "escalation_rules": True})
        svc2._get_ticket = AsyncMock(return_value={"tags": ["a"]})
        svc2._check_sla_compliance = AsyncMock()
        svc2._check_escalation = AsyncMock()
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc2.platform_integrations["teams"] = integration
        updated = _http_resp(200, {"ticket": {"id": "1", "status": "solved"}})
        cm = _acm(put_result=updated)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc2.update_ticket("1", {"status": "solved", "author_id": "a"},
                                         platform="teams", comment="done")
        assert r["success"] is True
        svc2._check_sla_compliance.assert_awaited_once()
        svc2._check_escalation.assert_awaited_once()
        integration.send_notification.assert_awaited_once()

        svc3 = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False,
            "sla_monitoring": False, "escalation_rules": False})
        svc3._get_ticket = AsyncMock(return_value={})
        cm = _acm(put_result=_http_resp(400, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc3.update_ticket("1", {})
        assert not r["success"]

        svc4 = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False})
        svc4._get_ticket = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc4.update_ticket("1", {})
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_get_tickets_pagination_and_errors(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        page1 = _http_resp(200, {"tickets": [{"id": "1", "status": "new"}],
                                 "next_page": "https://next"})
        page2 = _http_resp(200, {"tickets": [{"id": "2", "status": "solved"}]})
        responses = [page1, page2]
        client = MagicMock()
        client.get = AsyncMock(side_effect=responses)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            tickets = await svc.get_tickets({
                "status": "open", "priority": "high", "assignee_id": "a",
                "created_since": "2026-01-01", "limit": 500})
        assert len(tickets) == 2
        assert svc.analytics_metrics["open_tickets"] == 1
        assert svc.analytics_metrics["closed_tickets"] == 1

        client2 = MagicMock()
        client2.get = AsyncMock(return_value=_http_resp(400, {}))
        cm2 = MagicMock()
        cm2.__aenter__ = AsyncMock(return_value=client2)
        cm2.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            assert await svc.get_tickets() == []

        client3 = MagicMock()
        client3.get = AsyncMock(side_effect=RuntimeError("x"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client3)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            assert await svc.get_tickets() == []

    @pytest.mark.asyncio
    async def test_get_ticket_info_and_comment(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        with patch.object(svc, "_get_ticket", new=AsyncMock(return_value={"id": "1"})):
            assert (await svc.get_ticket_info("1"))["id"] == "1"

        cm = _acm(put_result=_http_resp(200, {"ticket": {"id": "1"}}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_ticket_comment("1", "body", public=False)
        assert r["success"] is True
        cm2 = _acm(put_result=_http_resp(400, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            r = await svc.create_ticket_comment("1", "body")
        assert not r["success"]
        client = MagicMock()
        client.put = AsyncMock(side_effect=RuntimeError("x"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            r = await svc.create_ticket_comment("1", "body")
        assert not r["success"]

    @pytest.mark.asyncio
    async def test_analytics_generators_with_data(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
            SupportAnalyticsType,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": False,
            "ai_response_suggestions": False})
        tickets = [
            {"id": "1", "priority": "urgent", "type": "incident",
             "response_time": 10, "resolution_time": 100,
             "satisfaction_rating": "5", "assignee_id": "a1", "escalated": True,
             "resolved_first_contact": False},
            {"id": "2", "priority": "low", "type": "question",
             "response_time": 5, "resolution_time": 50,
             "satisfaction_rating": "3", "assignee_id": "a1", "escalated": False,
             "resolved_first_contact": True},
        ]
        with patch.object(svc, "get_tickets", new=AsyncMock(return_value=tickets)):
            for atype in SupportAnalyticsType:
                r = await svc.generate_support_analytics(atype)
                assert r["success"] is True, atype
        r = await svc.generate_support_analytics("bogus")
        assert r["success"] is True
        assert r["analytics"]["metrics"]["error"] == "Unsupported analytics type"

    @pytest.mark.asyncio
    async def test_analyze_ticket_with_ai(self, zendesk_with_enterprise):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        ai = zendesk_with_enterprise.ai_enhanced_service
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={"suggested_priority": "high", "sentiment": "negative"}))
        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t",
                                                    "ai_service": ai})
        r = await svc._analyze_ticket_with_ai({"subject": "S", "description": "D"})
        assert r["suggested_priority"] == "high"

        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        r = await svc._analyze_ticket_with_ai({"priority": "normal"})
        assert r["suggested_priority"] == "normal"

        ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
        r = await svc._analyze_ticket_with_ai({})
        assert r["sentiment"] == "neutral"

    @pytest.mark.asyncio
    async def test_auto_assign_and_helpers(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        svc._get_available_agents = AsyncMock(return_value=[{"id": "a1"}, {"id": "a2"}])
        svc.agent_skills = {"a1": ["billing"]}
        svc._get_agent_workload = AsyncMock(return_value=2)
        assert await svc._auto_assign_ticket({"suggested_agent_skills": ["billing"]}) == "a1"
        svc._get_agent_workload = AsyncMock(return_value=9)
        svc.agent_skills = {"a2": ["billing"]}
        svc.analytics_metrics["agent_performance"]["a1"]["open_tickets"] = 5
        svc.analytics_metrics["agent_performance"]["a2"]["open_tickets"] = 1
        assert await svc._auto_assign_ticket({"suggested_agent_skills": ["billing"]}) == "a2"
        svc._get_available_agents = AsyncMock(return_value=[])
        assert await svc._auto_assign_ticket({"suggested_agent_skills": []}) is None
        svc._get_available_agents = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._auto_assign_ticket({}) is None

        from integrations.atom_zendesk_integration_service import AtomZendeskIntegrationService
        svc._get_available_agents = AtomZendeskIntegrationService._get_available_agents.__get__(
            svc, AtomZendeskIntegrationService)
        svc._get_auth_headers = Mock(return_value={})
        svc._get_ticket = AsyncMock()
        cm = _acm(get_result=_http_resp(200, {"users": [
            {"id": "a1", "role": "agent"}, {"id": "u1", "role": "end-user"}]}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            agents = await svc._get_available_agents()
        assert agents == [{"id": "a1", "role": "agent"}]
        cm2 = _acm(get_result=_http_resp(400, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            assert await svc._get_available_agents() == []
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("x"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            assert await svc._get_available_agents() == []

        from integrations.atom_zendesk_integration_service import AtomZendeskIntegrationService
        svc._get_agent_workload = AtomZendeskIntegrationService._get_agent_workload.__get__(
            svc, AtomZendeskIntegrationService)
        with patch.object(svc, "get_tickets", new=AsyncMock(return_value=[{}, {}])):
            assert await svc._get_agent_workload("a1") == 2
        with patch.object(svc, "get_tickets", new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc._get_agent_workload("a1") == 0

    @pytest.mark.asyncio
    async def test_get_ticket_cache_and_api_paths(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        cache = MagicMock()
        cache.get = AsyncMock(return_value={"id": "1"})
        cache.set = AsyncMock()
        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t",
                                                    "cache": cache})
        assert (await svc._get_ticket("1"))["id"] == "1"

        cache.get = AsyncMock(return_value=None)
        svc2 = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t",
                                                     "cache": cache})
        cm = _acm(get_result=_http_resp(200, {"ticket": {"id": "2"}}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            assert (await svc2._get_ticket("2"))["id"] == "2"
        cm2 = _acm(get_result=_http_resp(404, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            assert await svc2._get_ticket("2") is None
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError("x"))
        cm3 = MagicMock()
        cm3.__aenter__ = AsyncMock(return_value=client)
        cm3.__aexit__ = AsyncMock(return_value=False)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm3):
            assert await svc2._get_ticket("2") is None

    @pytest.mark.asyncio
    async def test_salesforce_sync_and_notify_methods(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "t", "enable_salesforce_integration": True})
        await svc._initialize_salesforce_integration()
        assert svc.salesforce_integration is None

        import sys
        import types
        fake_sf = types.ModuleType("atom_salesforce_integration")
        fake_sf.atom_salesforce_integration = MagicMock()
        sys.modules["atom_salesforce_integration"] = fake_sf
        try:
            await svc._initialize_salesforce_integration()
            assert svc.salesforce_integration is fake_sf.atom_salesforce_integration
        finally:
            del sys.modules["atom_salesforce_integration"]

        sf = MagicMock()
        sf.sync_ticket = AsyncMock()
        svc.salesforce_integration = sf
        await svc._sync_ticket_to_salesforce({"id": "1"})
        sf.sync_ticket.assert_awaited_once()
        svc.salesforce_integration = None
        await svc._sync_ticket_to_salesforce({"id": "1"})
        sf2 = MagicMock()
        sf2.sync_ticket = AsyncMock(side_effect=RuntimeError("x"))
        svc.salesforce_integration = sf2
        await svc._sync_ticket_to_salesforce({"id": "1"})

        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations["slack"] = integration
        await svc._notify_platform_ticket_created({"subject": "S"}, "slack")
        await svc._notify_platform_ticket_created({}, "nope")
        await svc._notify_platform_ticket_updated({"subject": "S"}, "slack")
        integration.send_notification.assert_awaited()

        await svc._check_sla_compliance({"priority": "urgent"})
        await svc._check_sla_compliance({"priority": "weird"})
        await svc._check_escalation({"priority": "high"})
        await svc._check_escalation({"priority": "low"})
        assert svc.analytics_metrics["escalation_rate"] > 0

        sec = MagicMock()
        sec.check = AsyncMock(return_value={"allowed": False, "reason": "no"})
        svc.enterprise_security = sec
        assert (await svc._perform_security_check({}))["passed"] is False
        sec.check = AsyncMock(return_value={"allowed": True})
        assert (await svc._perform_security_check({}))["passed"] is True
        sec.check = AsyncMock(side_effect=RuntimeError("x"))
        assert (await svc._perform_security_check({}))["passed"] is True

        autom = MagicMock()
        autom._handle_event_trigger = AsyncMock()
        svc.enterprise_automation = autom
        await svc._trigger_ticket_workflows({"id": "1"}, "created")
        autom._handle_event_trigger.assert_awaited_once()
        svc.enterprise_automation = None
        await svc._trigger_ticket_workflows({"id": "1"}, "created")
        autom._handle_event_trigger = AsyncMock(side_effect=RuntimeError("x"))
        svc.enterprise_automation = autom
        await svc._trigger_ticket_workflows({"id": "1"}, "created")

    @pytest.mark.asyncio
    async def test_auth_headers_and_connection(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        h = svc._get_auth_headers()
        assert h["Authorization"].startswith("Bearer")
        svc2 = AtomZendeskIntegrationService(config={
            "zendesk_api_token": "tok", "zendesk_username": "u"})
        h = svc2._get_auth_headers()
        assert h["Authorization"].startswith("Basic")
        svc3 = AtomZendeskIntegrationService(config={})
        with pytest.raises(Exception):
            svc3._get_auth_headers()

        cm = _acm(get_result=_http_resp(200, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            assert await svc._test_zendesk_connection() is True
        cm2 = _acm(get_result=_http_resp(500, {}))
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm2):
            with pytest.raises(Exception):
                await svc._test_zendesk_connection()

    @pytest.mark.asyncio
    async def test_status_close_and_cache(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        r = await svc.get_service_status()
        assert r["service"] == "zendesk_integration"
        svc.is_initialized = True
        r = await svc.get_service_status()
        assert r["status"] == "active"
        await svc.close()

        cache = MagicMock()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        svc2 = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t",
                                                     "cache": cache})
        await svc2._cache_ticket({"id": "1"})

        svc3 = AtomZendeskIntegrationService(config={"zendesk_oauth_token": "t"})
        svc3.zendesk_config = {}
        r = await svc3.get_service_status()
        assert "error" in r


# ============================================================================
# part 5 - remaining exception branches
# ============================================================================

class TestAtomHubspotEdge:
    @pytest.mark.asyncio
    async def test_initialize_failure_path(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        with patch.object(svc, "_test_hubspot_connection",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            assert await svc.initialize() is False

    @pytest.mark.asyncio
    async def test_create_contact_score_lifecycle_and_platform(self,
                                                              hubspot_with_enterprise):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        ai = hubspot_with_enterprise
        svc = AtomHubSpotIntegrationService(config={
            "hubspot_access_token": "t", "ai_service": ai.ai_enhanced_service})
        ai.ai_enhanced_service.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data={"lead_score": 85}))
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations["slack"] = integration
        svc.automation_flows = {
            "f1": {"trigger_event": "contact_created", "conditions": {},
                   "actions": [{"type": "send_email"}]}}
        cm = _acm(post_result=_http_resp(201, {"id": "1"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_contact({"email": "a@b.c"}, platform="slack")
        assert r["success"] is True
        assert r["lead_score"] == 85
        integration.send_notification.assert_awaited_once()

        ai.ai_enhanced_service.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data={"lead_score": 70}))
        cm = _acm(post_result=_http_resp(201, {"id": "2"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            await svc.create_contact({"email": "b@c.d"})
        assert svc.analytics_metrics["average_lead_score"] > 0

        ai.ai_enhanced_service.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data={"lead_score": 40}))
        cm = _acm(post_result=_http_resp(201, {"id": "3"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            await svc.create_contact({"email": "c@d.e"})

    @pytest.mark.asyncio
    async def test_ingestion_exception_paths(self, hubspot_with_enterprise):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )
        from datetime import datetime

        mod = hubspot_with_enterprise
        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        cm = _acm(post_result=_http_resp(201, {"id": "1"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_contact({"email": "a@b.c"})
        assert r["success"] is True
        cm = _acm(post_result=_http_resp(201, {"id": "c1"}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            r = await svc.create_campaign({"name": "C",
                                           "start_date": datetime(2026, 1, 1)})
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_generate_analytics_error_and_ai_insights(self,
                                                            hubspot_with_enterprise):
        from integrations.atom_hubspot_integration_service import (
            AnalyticsType,
            AtomHubSpotIntegrationService,
        )

        mod = hubspot_with_enterprise
        svc = AtomHubSpotIntegrationService(config={
            "hubspot_access_token": "t", "ai_service": mod.ai_enhanced_service})
        with patch.object(svc, "_generate_lead_conversion_analytics",
                          new=AsyncMock(side_effect=RuntimeError("x"))):
            r = await svc.generate_marketing_analytics(AnalyticsType.LEAD_CONVERSION)
        assert not r["success"]

        mod.ai_enhanced_service.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=True, output_data={"insight": "x"}))
        out = await svc._generate_ai_insights({"m": 1}, AnalyticsType.LEAD_SCORING)
        assert out["insight"] == "x"
        mod.ai_enhanced_service.process_ai_request = AsyncMock(
            return_value=SimpleNamespace(ok=False, output_data=None))
        out = await svc._generate_ai_insights({"m": 1}, AnalyticsType.LEAD_SCORING)
        assert out == {"insights": [], "recommendations": []}
        mod.ai_enhanced_service.process_ai_request = AsyncMock(
            side_effect=RuntimeError("x"))
        out = await svc._generate_ai_insights({"m": 1}, AnalyticsType.LEAD_SCORING)
        assert out == {"insights": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_rule_based_branches_and_exception(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        assert await svc._rule_based_lead_scoring(
            {"job_title": "Engineering Manager"}) >= 15.0
        assert await svc._rule_based_lead_scoring(
            {"job_title": "Senior Engineer"}) >= 10.0
        assert await svc._rule_based_lead_scoring(
            {"job_title": "Engineer", "source": "website"}) >= 10.0
        broken = MagicMock()
        broken.get = Mock(side_effect=RuntimeError("x"))
        assert await svc._rule_based_lead_scoring(broken) == 50.0

        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc2.analytics_metrics["total_contacts"] = 2
        with patch.object(svc2, "_rule_based_lead_scoring",
                          new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc2, "ai_service", None):
            with patch.object(svc2, "hubspot_config",
                              {"enable_lead_scoring": True}):
                score = await svc2._score_lead({"email": "a@b.c"})
        assert score == 50.0

    @pytest.mark.asyncio
    async def test_workflow_exception_paths(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc.hubspot_config["automation_workflows"] = True
        svc.automation_flows = {
            "f1": {"trigger_event": "contact_created", "conditions": {},
                   "actions": [{"type": "send_email"}, {"type": "add_to_list"},
                               {"type": "create_task"}, {"type": "update_properties"},
                               {"type": "unknown_action"}]}}
        with patch.object(svc, "_evaluate_workflow_conditions",
                          new=Mock(side_effect=RuntimeError("x"))):
            await svc._trigger_automation_workflows({"id": "1"}, "contact_created")

        svc2 = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        svc2.campaign_performance = MagicMock()
        svc2.campaign_performance.__setitem__ = Mock(side_effect=RuntimeError("x"))
        await svc2._trigger_campaign_workflows({"id": "c1"}, "created")

        broken = MagicMock()
        broken.get = Mock(side_effect=RuntimeError("x"))
        assert svc2._evaluate_workflow_conditions(broken, {}) is False

        broken_action = MagicMock()
        broken_action.get = Mock(side_effect=RuntimeError("x"))
        await svc2._execute_workflow({"actions": [broken_action]}, {"id": "1"})

        with patch("integrations.atom_hubspot_integration_service.logger.info",
                   side_effect=RuntimeError("x")):
            await svc2._send_automated_email({"id": "1"}, {})
            await svc2._add_contact_to_list({"id": "1"}, {})
            await svc2._create_marketing_task({"id": "1"}, {})
            await svc2._update_contact_properties({"id": "1"}, {})

        bad_integration = MagicMock()
        bad_integration.send_notification = AsyncMock(side_effect=RuntimeError("x"))
        svc2.platform_integrations["slack"] = bad_integration
        await svc2._notify_platform_lead_created({"id": "1"}, "slack")
        await svc2._notify_platform_campaign_created({"name": "C"}, "slack")

        with patch("integrations.atom_hubspot_integration_service.logger.info",
                   side_effect=RuntimeError("x")):
            await svc2.close()

    @pytest.mark.asyncio
    async def test_sync_full_sync_and_analytics_flow(self):
        import integrations.atom_hubspot_integration_service as mod
        from integrations.atom_hubspot_integration_service import (
            AnalyticsType,
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        for atype in [AnalyticsType.CAMPAIGN_PERFORMANCE, AnalyticsType.WEBSITE_TRAFFIC,
                      AnalyticsType.MARKETING_ROI, AnalyticsType.LEAD_SCORING,
                      AnalyticsType.AB_TESTING, AnalyticsType.SOCIAL_MEDIA_ENGAGEMENT,
                      AnalyticsType.EMAIL_PERFORMANCE]:
            r = await svc.generate_marketing_analytics(atype)
            assert r["success"] is True, atype


class TestFreshdeskEdge:
    @pytest.mark.asyncio
    async def test_init_no_config_and_except_branches(self):
        import integrations.freshdesk_service as fd

        s = fd.FreshdeskService()
        assert s.api_key is None
        with patch.object(s, "_handle_request", new=AsyncMock(side_effect=RuntimeError("x"))):
            for coro in [s.get_contacts(), s.get_contact(1), s.update_contact(1, {}),
                         s.create_company({}), s.get_companies(), s.get_company(1),
                         s.get_agents(), s.get_agent(1), s.get_groups(), s.get_group(1)]:
                with pytest.raises(RuntimeError):
                    await coro

    @pytest.mark.asyncio
    async def test_upload_attachment_success(self):
        import integrations.freshdesk_service as fd

        svc = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                          "freshdesk_domain": "acme"})
        with patch.object(svc, "_handle_request",
                          new=AsyncMock(return_value={"id": 1})):
            r = await svc.upload_attachment(b"data", "f.txt")
        assert r["id"] == 1

    @pytest.mark.asyncio
    async def test_sync_branches(self):
        import integrations.freshdesk_service as fd

        db = MagicMock()
        existing = Mock()
        db.query.return_value.filter_by.return_value.first.side_effect = [None, existing]
        svc = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                          "freshdesk_domain": "acme"})
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_tickets", new=AsyncMock(return_value=[{}, {}])), \
             patch.object(svc, "get_contacts", new=AsyncMock(return_value=[{}])):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert r["success"] is True
        existing.value = 3.0

        db2 = MagicMock()
        db2.query.return_value.filter_by.return_value.first.return_value = None
        db2.commit = Mock(side_effect=RuntimeError("db"))
        with patch("core.database.SessionLocal", return_value=db2), \
             patch.object(svc, "get_tickets", new=AsyncMock(return_value=[])), \
             patch.object(svc, "get_contacts", new=AsyncMock(return_value=[])):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert not r["success"]

        with patch("core.database.SessionLocal", side_effect=RuntimeError("conn")):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert not r["success"]

        with patch.object(svc, "sync_to_postgres_cache",
                          new=AsyncMock(return_value={"success": True})):
            r = await svc.full_sync("ws-1")
        assert r["success"] is True

    @pytest.mark.asyncio
    async def test_sync_ticket_fetch_exceptions(self):
        import integrations.freshdesk_service as fd

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        svc = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                          "freshdesk_domain": "acme"})
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_tickets", new=AsyncMock(side_effect=RuntimeError("x"))), \
             patch.object(svc, "get_contacts", new=AsyncMock(side_effect=RuntimeError("y"))):
            r = await svc.sync_to_postgres_cache("ws-1")
        assert r["success"] is True and r["metrics_synced"] == 2


class TestSalesforceEdge:
    def test_service_mock_and_import_error_shadow(self):
        import integrations.salesforce_routes as routes

        m = routes.SalesforceServiceMock()
        assert m.instance_url == "mock_instance_url"

    @pytest.mark.asyncio
    async def test_unavailable_and_error_branches(self):
        import integrations.salesforce_routes as routes
        from fastapi import HTTPException

        sf = Mock()
        routes_spec = [
            ("get_salesforce_account", dict(account_id="001xx", access_token="t")),
            ("create_salesforce_account", dict(name="Acme", access_token="t")),
            ("get_salesforce_contacts", dict(limit=10, access_token="t")),
            ("create_salesforce_contact",
             dict(first_name="A", last_name="B", email="a@b.c", access_token="t")),
            ("get_salesforce_opportunities", dict(limit=10, access_token="t")),
            ("create_salesforce_opportunity",
             dict(name="O", account_id="a", stage="s", amount=1.0,
                  close_date="2026-01-01", access_token="t")),
            ("get_salesforce_leads", dict(limit=10, access_token="t")),
            ("create_salesforce_lead",
             dict(first_name="A", last_name="B", company="C",
                  email="a@b.c", access_token="t")),
            ("search_salesforce", dict(query="q", object_types=["Account"],
                                       access_token="t")),
            ("get_sales_pipeline_analytics", dict(access_token="t")),
            ("get_leads_analytics", dict(access_token="t")),
            ("get_salesforce_user_profile", dict(access_token="t")),
        ]
        with patch.object(routes, "SALESFORCE_AVAILABLE", False):
            for name, kwargs in routes_spec:
                with pytest.raises(HTTPException) as ei:
                    await getattr(routes, name)(**kwargs)
                assert ei.value.status_code == 503, name

        for name, kwargs in routes_spec:
            with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
                 patch.object(routes, "get_salesforce_client_from_env",
                              side_effect=RuntimeError("x")):
                r = await getattr(routes, name)(**kwargs)
            assert r["ok"] is False, name

        # health 500 branch (response construction raises)
        class _BadDT:
            @staticmethod
            def now(*a, **k):
                raise RuntimeError("x")
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "datetime", _BadDT):
            with pytest.raises(HTTPException) as ei:
                await routes.salesforce_health_check()
        assert ei.value.status_code == 500

        # get_salesforce_client_from_env except branch
        with patch.object(routes.salesforce_auth_handler, "is_token_valid",
                          return_value=True), \
             patch.object(routes, "Salesforce",
                          side_effect=RuntimeError("x")):
            assert routes.get_salesforce_client_from_env() is None

    @pytest.mark.asyncio
    async def test_ingestion_error_paths_opps_leads(self):
        import integrations.salesforce_routes as routes

        sf = Mock()
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_opportunities",
                          new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record",
                          side_effect=RuntimeError("boom")):
            r = await routes.get_salesforce_opportunities(limit=10, access_token="t")
        assert r["ok"] is True
        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env", return_value=sf), \
             patch.object(routes, "list_leads", new=AsyncMock(return_value=[{"Id": "1"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record",
                          side_effect=RuntimeError("boom")):
            r = await routes.get_salesforce_leads(limit=10, access_token="t")
        assert r["ok"] is True
