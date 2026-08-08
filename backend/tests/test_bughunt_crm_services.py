"""Bug-hunt tests (TDD RED->GREEN) for CRM integration services.

Covered modules:
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
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest


# ============================================================================
# helpers
# ============================================================================

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


def _async_client_mock(post_result=None, get_result=None, put_result=None):
    """Patch target for httpx.AsyncClient used as `async with`."""
    client = MagicMock()
    client.post = AsyncMock(return_value=post_result or _http_resp(200, {}))
    client.get = AsyncMock(return_value=get_result or _http_resp(200, {}))
    client.put = AsyncMock(return_value=put_result or _http_resp(200, {}))
    client.delete = AsyncMock(return_value=_http_resp(204, {}))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ============================================================================
# 1. hubspot_routes.py:249 - `os` never imported at module level -> NameError
#    in HubSpotService.__init__, so EVERY /api/hubspot route 500s.
# ============================================================================

class TestHubspotRoutesO:
    def test_hubspot_service_instantiates_without_nameerror(self):
        import integrations.hubspot_routes as routes

        with patch.dict("os.environ", {}, clear=False):
            try:
                svc = routes.HubSpotService()
            except NameError:
                pytest.fail(
                    "HubSpotService() raised NameError: 'os' is not defined. "
                    "Every /api/hubspot route 500s."
                )
        assert svc is not None

    @pytest.mark.asyncio
    async def test_health_route_works(self):
        import integrations.hubspot_routes as routes

        with patch.object(routes.HubSpotService, "health_check_wrapper",
                          new=AsyncMock(return_value={"ok": True, "status": "healthy"})):
            result = await routes.health_check()
        assert result["ok"] is True


# ============================================================================
# 2. salesforce_routes.py - `logger` never defined (logging.getLogger missing)
#    -> NameError in ingestion error path and governance error path.
# ============================================================================

class TestSalesforceRoutesLogger:
    @pytest.mark.asyncio
    async def test_accounts_route_handles_ingestion_failure(self):
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env",
                          return_value=Mock()), \
             patch.object(routes, "list_accounts",
                          new=AsyncMock(return_value=[{"Id": "001x", "Name": "Acme"}])), \
             patch.object(routes.atom_ingestion_pipeline, "ingest_record",
                          side_effect=RuntimeError("pipeline down")):
            result = await routes.get_salesforce_accounts(limit=10, access_token="tok")
        # ingestion failure must NOT 500 -> structured ok response
        assert result["ok"] is True
        assert result["data"]["accounts"][0]["Name"] == "Acme"

    @pytest.mark.asyncio
    async def test_create_account_governance_error_does_not_nameerror(self):
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "SALESFORCE_GOVERNANCE_ENABLED", True), \
             patch.object(routes, "EMERGENCY_GOVERNANCE_BYPASS", False), \
             patch.object(routes, "get_salesforce_client_from_env",
                          return_value=Mock()), \
             patch.object(routes, "with_governance_check",
                          new=AsyncMock(side_effect=RuntimeError("gov down"))), \
             patch.object(routes, "create_account",
                          new=AsyncMock(return_value={"Id": "001x"})):
            result = await routes.create_salesforce_account(
                name="Acme", db=Mock(), access_token="tok"
            )
        assert result["ok"] is True

    def test_module_has_logger(self):
        import integrations.salesforce_routes as routes

        assert hasattr(routes, "logger")


# ============================================================================
# 2b. salesforce_routes.py - health must degrade (not 500) when the client
#     cannot be initialized; error responses must not leak str(e)
# ============================================================================

class TestSalesforceHealthDegradation:
    @pytest.mark.asyncio
    async def test_health_degrades_when_client_init_raises(self):
        """Client init failure -> degraded, not a 500 RuntimeError."""
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env",
                          side_effect=RuntimeError("sf client init failed")):
            result = await routes.salesforce_health_check()

        assert result["ok"] is True
        assert result["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_accounts_error_response_does_not_leak_exception(self):
        """str(e) must not reach the client in the error payload."""
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env",
                          return_value=Mock()), \
             patch.object(routes, "list_accounts",
                          new=AsyncMock(side_effect=ValueError("secret-internal-detail"))):
            result = await routes.get_salesforce_accounts(limit=10, access_token="tok")

        assert result["ok"] is False
        assert "secret-internal-detail" not in json.dumps(result)

    @pytest.mark.asyncio
    async def test_soql_error_response_does_not_leak_exception(self):
        """SOQL query failures must not leak exception internals either."""
        import integrations.salesforce_routes as routes

        with patch.object(routes, "SALESFORCE_AVAILABLE", True), \
             patch.object(routes, "get_salesforce_client_from_env",
                          return_value=Mock()), \
             patch.object(routes, "execute_soql_query",
                          new=AsyncMock(side_effect=RuntimeError("soql-internal-detail"))):
            result = await routes.get_salesforce_account(
                account_id="001000000000001AAA", access_token="tok"
            )

        assert "soql-internal-detail" not in json.dumps(result)


# ============================================================================
# 2c. salesforce + hubspot routers must require user auth (no anonymous data)
# ============================================================================

class TestIntegrationRouterAuth:
    def test_salesforce_router_requires_user_auth(self):
        import integrations.salesforce_routes as routes

        assert routes.router.dependencies, (
            "salesforce router has no user-auth dependency — /api/v1/integrations/salesforce/* "
            "is reachable anonymously"
        )

    def test_hubspot_router_requires_user_auth(self):
        import integrations.hubspot_routes as routes

        assert routes.router.dependencies, (
            "hubspot router has no user-auth dependency — /api/v1/integrations/hubspot/* "
            "is reachable anonymously"
        )


# ============================================================================
# 3. jira_service.py:689 - `asyncio` never imported -> execute_operation always
#    raises NameError even when the underlying API call succeeds.
# ============================================================================

class TestJiraExecuteOperation:
    @pytest.mark.asyncio
    async def test_execute_operation_success_path(self):
        from integrations.jira_service import JiraService

        svc = JiraService(config={"base_url": "https://x.atlassian.net"})
        svc.session.request = Mock(return_value=_http_resp(200, {"values": [{"id": 1}]}))

        result = await svc.execute_operation("get_projects", {"max_results": 5})
        assert result["success"] is True
        assert result["result"]["values"][0]["id"] == 1


# ============================================================================
# 4. atom_hubspot_integration_service.py:385,498 - hubspot_config never
#    contains 'enable_enterprise_features' -> KeyError on every
#    create_contact/create_campaign.
# ============================================================================

class TestAtomHubspotCreate:
    @pytest.fixture(autouse=True)
    def _no_throttle(self):
        with patch("integrations.atom_hubspot_integration_service.rate_limiter") as rl, \
             patch("integrations.atom_hubspot_integration_service.circuit_breaker") as cb:
            rl.is_rate_limited = AsyncMock(return_value=(False, 1000))
            cb.is_enabled = AsyncMock(return_value=True)
            yield

    @pytest.mark.asyncio
    async def test_create_contact_succeeds_with_mocked_api(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        contact_resp = _http_resp(201, {"id": "123", "properties": {"email": "a@b.c"}})
        cm = _async_client_mock(post_result=contact_resp)

        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.create_contact(
                {"email": "a@b.c", "first_name": "Ann", "last_name": "Lee"}
            )
        assert result["success"] is True, result
        assert result["contact_id"] == "123"

    @pytest.mark.asyncio
    async def test_create_campaign_succeeds_with_mocked_api(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )
        from datetime import datetime

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        campaign_resp = _http_resp(201, {"id": "c1"})
        cm = _async_client_mock(post_result=campaign_resp)

        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.create_campaign(
                {"name": "Q4", "start_date": datetime(2026, 1, 1),
                 "end_date": datetime(2026, 3, 1)}
            )
        assert result["success"] is True, result
        assert result["campaign_id"] == "c1"


# ============================================================================
# 5. atom_hubspot_integration_service.py - initialize() calls 9 phantom
#    methods (_setup_webhooks, _setup_lead_scoring, ...) -> always False.
# ============================================================================

class TestAtomHubspotInitialize:
    @pytest.mark.asyncio
    async def test_initialize_returns_true(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        cm = _async_client_mock(get_result=_http_resp(200, {}))
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            ok = await svc.initialize()
        assert ok is True
        assert svc.is_initialized is True


# ============================================================================
# 6. atom_hubspot_integration_service.py - except handlers reference undefined
#    audit_ctx (NameError masks the real error); _score_lead must return a
#    float score (fallback), never crash when AI service is absent.
# ============================================================================

class TestAtomHubspotScoreLead:
    @pytest.mark.asyncio
    async def test_score_lead_falls_back_to_rule_based_without_ai(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        score = await svc._score_lead({"email": "x@corp.com", "company": "Acme"})
        assert isinstance(score, float)
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_rule_based_scoring_ranges(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        low = await svc._rule_based_lead_scoring({"email": "a@gmail.com"})
        high = await svc._rule_based_lead_scoring(
            {"company": "Acme", "job_title": "CEO", "email": "ceo@acme.com",
             "phone": "555", "website": "acme.com", "source": "referral"}
        )
        assert isinstance(low, float)
        assert 0 <= low <= high <= 100

    @pytest.mark.asyncio
    async def test_create_contact_increments_analytics_and_scores(self):
        from integrations.atom_hubspot_integration_service import (
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "tok"})
        contact_resp = _http_resp(201, {"id": "999"})
        cm = _async_client_mock(post_result=contact_resp)
        with patch("integrations.atom_hubspot_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.create_contact({"email": "z@corp.com"})
        assert result["success"] is True
        assert svc.analytics_metrics["total_contacts"] == 1


# ============================================================================
# 7. hubspot_service.py:658 - sync_to_postgres_cache uses tenant_id= on
#    IntegrationMetric (real column is workspace_id) -> always fails.
# ============================================================================

class TestHubspotServiceSync:
    @pytest.mark.asyncio
    async def test_sync_to_postgres_cache_uses_workspace_id(self):
        import integrations.hubspot_service as hs

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        db_session_patch = patch("core.database.SessionLocal", return_value=db)

        svc = hs.HubSpotService(config={"access_token": "tok"})
        with db_session_patch, \
             patch.object(svc, "get_analytics", new=AsyncMock(return_value={
                 "total_revenue": 100.0, "deal_count": 2, "contact_count": 5,
             })):
            result = await svc.sync_to_postgres_cache("ws-1")

        assert result["success"] is True, result
        assert result["metrics_synced"] == 3


# ============================================================================
# 8. freshdesk_service.py:661 - same tenant_id/workspace_id column bug.
# ============================================================================

class TestFreshdeskSync:
    @pytest.mark.asyncio
    async def test_sync_to_postgres_cache_uses_workspace_id(self):
        import integrations.freshdesk_service as fd

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        svc = fd.FreshdeskService(config={"freshdesk_api_key": "k",
                                          "freshdesk_domain": "acme"})
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_tickets", new=AsyncMock(return_value=[{}, {}])), \
             patch.object(svc, "get_contacts", new=AsyncMock(return_value=[{}])):
            result = await svc.sync_to_postgres_cache("ws-1")

        assert result["success"] is True, result
        assert result["metrics_synced"] == 2


# ============================================================================
# 9. trello_service.py:441,451 - same tenant_id/workspace_id column bug.
# ============================================================================

class TestTrelloSync:
    def test_sync_to_postgres_cache_uses_workspace_id(self):
        from integrations.trello_service import TrelloService

        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None

        svc = TrelloService(config={"api_key": "k", "access_token": "t"})
        with patch("core.database.SessionLocal", return_value=db), \
             patch.object(svc, "get_boards", return_value=[{}, {}]):
            result = svc.sync_to_postgres_cache("ws-1")

        assert result["success"] is True, result
        assert result["metrics_synced"] == 1


# ============================================================================
# 10. atom_zendesk_integration_service.py:224 - async _initialize_salesforce_
#     integration called without await in __init__ -> un-awaited coroutine.
# ============================================================================

class TestZendeskInit:
    def test_salesforce_integration_is_not_a_coroutine(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={})
        assert not asyncio.iscoroutine(svc.salesforce_integration)


# ============================================================================
# 11. atom_zendesk_integration_service.py - 14 phantom methods
#     (_sync_ticket_to_salesforce, _check_sla_compliance, _check_escalation,
#     _notify_platform_*, _generate_*_analytics, _generate_ai_insights,
#     _perform_security_check) -> create_ticket / update_ticket /
#     generate_support_analytics crash with AttributeError.
# ============================================================================

class TestZendeskTicketOps:
    @pytest.fixture(autouse=True)
    def _no_throttle(self):
        with patch("integrations.atom_zendesk_integration_service.rate_limiter") as rl, \
             patch("integrations.atom_zendesk_integration_service.circuit_breaker") as cb:
            rl.is_rate_limited = AsyncMock(return_value=(False, 1000))
            cb.is_enabled = AsyncMock(return_value=True)
            yield

    @pytest.mark.asyncio
    async def test_create_ticket_succeeds(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "tok",
            "enable_salesforce_integration": False,
            "ticket_auto_assignment": False,
            "priority_auto_classification": False,
            "sentiment_analysis": False,
        })
        ticket_resp = _http_resp(201, {"ticket": {"id": "42", "subject": "hi"}})
        cm = _async_client_mock(post_result=ticket_resp)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.create_ticket(
                {"subject": "Help", "description": "Please", "requester_email": "a@b.c"}
            )
        assert result["success"] is True, result
        assert result["ticket_id"] == "42"

    @pytest.mark.asyncio
    async def test_update_ticket_succeeds(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "tok",
            "enable_salesforce_integration": False,
            "sla_monitoring": False,
            "escalation_rules": False,
        })
        updated_resp = _http_resp(200, {"ticket": {"id": "7", "status": "solved"}})
        cm = _async_client_mock(get_result=_http_resp(200, {"ticket": {"id": "7"}}),
                                put_result=updated_resp)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.update_ticket("7", {"status": "solved"}, comment="done")
        assert result["success"] is True, result
        assert result["ticket"]["status"] == "solved"

    @pytest.mark.asyncio
    async def test_generate_support_analytics_all_types(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
            SupportAnalyticsType,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "tok",
            "enable_salesforce_integration": False,
            "ai_response_suggestions": False,
        })
        with patch.object(svc, "get_tickets", new=AsyncMock(return_value=[])):
            for atype in SupportAnalyticsType:
                result = await svc.generate_support_analytics(atype)
                assert result["success"] is True, (atype, result)
                assert "metrics" in result["analytics"]

    @pytest.mark.asyncio
    async def test_create_ticket_ai_analysis_fallback_without_ai(self):
        from integrations.atom_zendesk_integration_service import (
            AtomZendeskIntegrationService,
        )

        svc = AtomZendeskIntegrationService(config={
            "zendesk_oauth_token": "tok",
            "enable_salesforce_integration": False,
            "ticket_auto_assignment": False,
        })
        ticket_resp = _http_resp(201, {"ticket": {"id": "1"}})
        cm = _async_client_mock(post_result=ticket_resp)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   return_value=cm):
            result = await svc.create_ticket({"subject": "S", "description": "D"})
        assert result["success"] is True, result


# ============================================================================
# 12. hubspot_service.py - duplicate health_check (first def shadowed/dead).
#     Sanity: health_check returns the documented shape.
# ============================================================================

class TestHubspotServiceHealth:
    @pytest.mark.asyncio
    async def test_health_check_returns_ok_shape(self):
        import integrations.hubspot_service as hs

        svc = hs.HubSpotService(config={})
        result = await svc.health_check()
        assert result["ok"] is True
        assert result["status"] == "healthy"


# ============================================================================
# 13. atom_hubspot_integration_service.py - generate_marketing_analytics
#     calls 9 phantom _generate_*_analytics methods -> always fails.
# ============================================================================

class TestAtomHubspotAnalytics:
    @pytest.mark.asyncio
    async def test_generate_marketing_analytics_works_for_all_types(self):
        from integrations.atom_hubspot_integration_service import (
            AnalyticsType,
            AtomHubSpotIntegrationService,
        )

        svc = AtomHubSpotIntegrationService(config={"hubspot_access_token": "t"})
        for atype in AnalyticsType:
            r = await svc.generate_marketing_analytics(atype)
            assert r["success"] is True, (atype, r)
