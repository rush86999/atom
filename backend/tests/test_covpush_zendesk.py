"""Coverage push + bug-fix tests for integrations.atom_zendesk_integration_service.

Covers ticket CRUD, analytics generators, AI analysis, auto-assignment,
salesforce sync, platform notifications, SLA/escalation checks, and the
module import block. All external HTTP/OAuth calls mocked.
"""
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_zendesk_integration_service as zdmod


@pytest.fixture(autouse=True)
def _allow_governance_gates():
    with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=True)), \
         patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(False, 99))):
        yield


def _zd_config(**overrides):
    cfg = {
        "zendesk_subdomain": "test",
        "zendesk_api_token": "test-token",
        "zendesk_username": "user@test",
        "zendesk_oauth_token": None,
        "enable_salesforce_integration": False,
        "ticket_auto_assignment": False,
        "priority_auto_classification": False,
        "sentiment_analysis": False,
        "ai_response_suggestions": False,
        "sla_monitoring": False,
        "escalation_rules": False,
        "customer_journey_tracking": False,
        "enable_enterprise_features": False,
    }
    cfg.update(overrides)
    return cfg


def _svc(**cfg):
    return zdmod.AtomZendeskIntegrationService(config=_zd_config(**cfg))


def _ticket(**kw):
    data = {
        "id": "t-1", "subject": "Help", "description": "Need help",
        "requester_name": "Alice", "requester_email": "alice@example.com",
    }
    data.update(kw)
    return data


def _http_client_patch(get=None, post=None, put=None):
    return patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient")


class TestModuleImportAndGlobals:
    def test_reload_with_stubbed_services(self):
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
            "atom_discord_integration": ["atom_discord_integration"],
            "atom_enterprise_security_service": ["atom_enterprise_security_service"],
            "atom_google_chat_integration": ["atom_google_chat_integration"],
            "atom_slack_integration": ["atom_slack_integration"],
            "atom_teams_integration": ["atom_teams_integration"],
            "atom_telegram_integration": ["atom_telegram_integration"],
            "atom_whatsapp_integration": ["atom_whatsapp_integration"],
            "atom_workflow_automation_service": ["atom_workflow_automation_service", "AutomationPriority", "AutomationStatus"],
            "atom_zoom_integration": ["atom_zoom_integration"],
            "atom_salesforce_integration": ["atom_salesforce_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        try:
            with patch.dict(sys.modules, stubs):
                importlib.reload(zdmod)
                svc = zdmod.AtomZendeskIntegrationService(config={})
                assert len(svc.platform_integrations) == 7
                assert svc.enterprise_security is not None
                assert svc.enterprise_automation is not None
                assert svc.ai_service is not None
                assert zdmod._zendesk_config.get("security_service") is not None
                assert zdmod._zendesk_config.get("automation_service") is not None
                assert zdmod._zendesk_config.get("ai_service") is not None
        finally:
            importlib.reload(zdmod)


class TestAuthHeaders:
    def test_oauth_token_headers(self):
        svc = _svc(zendesk_oauth_token="oauth-tok")
        headers = svc._get_auth_headers()
        assert headers["Authorization"] == "Bearer oauth-tok"

    def test_api_token_headers(self):
        svc = _svc(zendesk_username="u", zendesk_api_token="tok")
        headers = svc._get_auth_headers()
        assert headers["Authorization"].startswith("Basic ")

    def test_no_auth_method_raises(self):
        svc = _svc(zendesk_api_token=None)
        with pytest.raises(Exception):
            svc._get_auth_headers()


class TestInitialize:
    async def test_initialize_with_salesforce(self):
        salesforce_mod = MagicMock()
        salesforce_mod.atom_salesforce_integration = MagicMock()
        with patch.dict(sys.modules, {"atom_salesforce_integration": salesforce_mod}):
            svc = _svc(enable_salesforce_integration=True)
            with patch.object(svc, "_test_zendesk_connection", AsyncMock(return_value=True)):
                assert await svc.initialize() is True
            assert svc.is_initialized
            assert svc.salesforce_integration is salesforce_mod.atom_salesforce_integration

    async def test_initialize_salesforce_import_error(self):
        sys.modules.pop("atom_salesforce_integration", None)
        svc = _svc(enable_salesforce_integration=True)
        with patch.object(svc, "_test_zendesk_connection", AsyncMock(return_value=True)):
            assert await svc.initialize() is True
        assert svc.salesforce_integration is None

    async def test_initialize_connection_failure(self):
        svc = _svc()
        with patch.object(svc, "_test_zendesk_connection", AsyncMock(side_effect=RuntimeError("down"))):
            assert await svc.initialize() is False

    async def test_setup_stubs(self):
        svc = _svc()
        assert await svc._initialize_salesforce_connection() is True
        await svc._setup_webhooks()
        await svc._setup_ticket_workflows()
        await svc._setup_escalation_rules()
        assert await svc._setup_enterprise_features() is True
        assert await svc._setup_security_and_compliance() is True
        assert await svc._load_existing_data() is True
        assert await svc._start_monitoring() is True


class TestCreateTicket:
    async def test_security_check_denied(self):
        security = MagicMock()
        security.check = AsyncMock(return_value={"allowed": False, "reason": "blocked by policy"})
        svc = _svc(enable_enterprise_features=True, security_service=security)
        result = await svc.create_ticket(_ticket())
        assert result["success"] is False
        assert result["error"] == "blocked by policy"
        security.check.assert_awaited_once()

    async def test_ai_analysis_applied(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
            "atom_enterprise_security_service": ["atom_enterprise_security_service"],
            "atom_workflow_automation_service": ["atom_workflow_automation_service", "AutomationPriority", "AutomationStatus"],
            "atom_slack_integration": ["atom_slack_integration"],
            "atom_zoom_integration": ["atom_zoom_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai_response = MagicMock()
            ai_response.ok = True
            ai_response.output_data = {
                "suggested_priority": "high", "sentiment": "positive",
                "urgency_score": 0.9, "complexity_score": 0.3,
                "suggested_agent_skills": ["billing"], "response_suggestion": "refund",
                "estimated_resolution_time": 30,
            }
            ai.process_ai_request = AsyncMock(return_value=ai_response)
            svc = mod.AtomZendeskIntegrationService(
                config=_zd_config(priority_auto_classification=True, ai_service=ai))
            fake = MagicMock()
            fake.status_code = 201
            fake.json.return_value = {"ticket": {"id": "t-1"}}
            with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
                client.return_value.__aenter__.return_value.post.return_value = fake
                result = await svc.create_ticket(_ticket())
            assert result["success"] is True
            ai.process_ai_request.assert_awaited_once()
        finally:
            importlib.reload(zdmod)

    async def test_ai_analysis_fallback_when_response_not_ok(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name in ["ai_enhanced_service", "atom_ai_integration"]:
            m = MagicMock()
            setattr(m, "ai_enhanced_service", MagicMock())
            stubs[name] = m
        stubs["ai_enhanced_service"].AIRequest = MagicMock()
        stubs["ai_enhanced_service"].AIResponse = MagicMock()
        stubs["ai_enhanced_service"].AIModelType = MagicMock()
        stubs["ai_enhanced_service"].AIServiceType = MagicMock()
        stubs["ai_enhanced_service"].AITaskType = MagicMock()
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai_response = MagicMock()
            ai_response.ok = False
            ai_response.output_data = None
            ai.process_ai_request = AsyncMock(return_value=ai_response)
            svc = mod.AtomZendeskIntegrationService(
                config=_zd_config(priority_auto_classification=True, ai_service=ai))
            suggestions = await svc._analyze_ticket_with_ai(_ticket())
            assert suggestions["suggested_priority"] == "normal"
            assert suggestions["sentiment"] == "neutral"
        finally:
            importlib.reload(zdmod)

    async def test_ai_analysis_exception_returns_fallback(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai.process_ai_request = AsyncMock(side_effect=RuntimeError("model down"))
            svc = mod.AtomZendeskIntegrationService(
                config=_zd_config(priority_auto_classification=True, ai_service=ai))
            suggestions = await svc._analyze_ticket_with_ai(_ticket())
            assert suggestions["suggested_priority"] == "normal"
            assert suggestions["sentiment"] == "neutral"
        finally:
            importlib.reload(zdmod)

    async def test_auto_assignment_adds_assignee(self):
        svc = _svc(ticket_auto_assignment=True)
        svc._auto_assign_ticket = AsyncMock(return_value="agent-1")
        fake = MagicMock()
        fake.status_code = 201
        fake.json.return_value = {"ticket": {"id": "t-1"}}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            post = client.return_value.__aenter__.return_value.post
            post.return_value = fake
            result = await svc.create_ticket(_ticket())
        assert result["success"] is True
        sent = post.call_args.kwargs["json"]
        assert sent["ticket"]["assignee_id"] == "agent-1"

    async def test_full_integration_paths(self):
        cache = MagicMock()
        cache.set = AsyncMock()
        automation = MagicMock()
        automation._handle_event_trigger = AsyncMock()
        security = MagicMock()
        security.check = AsyncMock(return_value={"allowed": True})
        svc = _svc(enable_enterprise_features=True, cache=cache,
                   automation_service=automation, security_service=security,
                   sla_monitoring=True, escalation_rules=True)
        svc.salesforce_integration = MagicMock()
        svc.salesforce_integration.sync_ticket = AsyncMock()
        svc.platform_integrations["slack"] = MagicMock()
        svc.platform_integrations["slack"].send_notification = AsyncMock()
        fake = MagicMock()
        fake.status_code = 201
        fake.json.return_value = {"ticket": {"id": "t-1", "subject": "Help"}}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.post.return_value = fake
            result = await svc.create_ticket(_ticket(), platform="slack")
        assert result["success"] is True
        cache.set.assert_awaited_once()
        svc.salesforce_integration.sync_ticket.assert_awaited_once()
        svc.platform_integrations["slack"].send_notification.assert_awaited_once()
        automation._handle_event_trigger.assert_awaited_once()
        assert svc.analytics_metrics["tickets_created_today"] == 1
        assert svc.analytics_metrics["ticket_volume_by_channel"]["slack"] == 1

    async def test_circuit_breaker_open(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            result = await svc.create_ticket(_ticket())
        assert result["success"] is False
        assert "temporarily disabled" in result["error"]

    async def test_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            result = await svc.create_ticket(_ticket())
        assert result["success"] is False
        assert "Rate limit" in result["error"]

    async def test_generic_error_message_no_leak(self):
        svc = _svc()
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("secret-internal-detail")):
            result = await svc.create_ticket(_ticket())
        assert result["success"] is False
        assert "secret-internal-detail" not in result["error"]


class TestUpdateTicket:
    async def test_full_update_with_comment_and_integrations(self):
        cache = MagicMock()
        cache.set = AsyncMock()
        automation = MagicMock()
        automation._handle_event_trigger = AsyncMock()
        svc = _svc(cache=cache, automation_service=automation,
                   sla_monitoring=True, escalation_rules=True)
        svc._get_ticket = AsyncMock(return_value={"id": "t-1", "tags": ["a"]})
        svc.salesforce_integration = MagicMock()
        svc.salesforce_integration.sync_ticket = AsyncMock()
        svc.platform_integrations["slack"] = MagicMock()
        svc.platform_integrations["slack"].send_notification = AsyncMock()
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {"ticket": {"id": "t-1", "priority": "urgent"}}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            put = client.return_value.__aenter__.return_value.put
            put.return_value = fake
            result = await svc.update_ticket(
                "t-1", {"status": "open", "author_id": "a-1", "public_comment": False},
                platform="slack", comment="please update")
        assert result["success"] is True
        sent = put.call_args.kwargs["json"]
        assert sent["ticket"]["comment"]["body"] == "please update"
        cache.set.assert_awaited_once()
        svc.salesforce_integration.sync_ticket.assert_awaited_once()
        svc.platform_integrations["slack"].send_notification.assert_awaited_once()
        automation._handle_event_trigger.assert_awaited_once()

    async def test_update_api_error(self):
        svc = _svc()
        svc._get_ticket = AsyncMock(return_value={"id": "t-1"})
        fake = MagicMock()
        fake.status_code = 500
        fake.text = "boom"
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.put.return_value = fake
            result = await svc.update_ticket("t-1", {"status": "open"})
        assert result["success"] is False
        assert "500" in result["error"]

    async def test_update_exception_generic(self):
        svc = _svc()
        svc._get_ticket = AsyncMock(return_value={"id": "t-1"})
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("secret-internal-detail")):
            result = await svc.update_ticket("t-1", {"status": "open"})
        assert result["success"] is False
        assert "secret-internal-detail" not in result["error"]

    async def test_update_ticket_not_found(self):
        svc = _svc()
        svc._get_ticket = AsyncMock(return_value=None)
        result = await svc.update_ticket("t-99", {"status": "open"})
        assert result["success"] is False

    async def test_update_ticket_circuit_breaker(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            result = await svc.update_ticket("t-1", {"status": "open"})
        assert result["success"] is False
        assert "temporarily disabled" in result["error"]

    async def test_update_ticket_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            result = await svc.update_ticket("t-1", {"status": "open"})
        assert result["success"] is False
        assert "Rate limit" in result["error"]


class TestGetTickets:
    async def test_pagination_and_filters(self):
        svc = _svc()
        page1 = MagicMock()
        page1.status_code = 200
        page1.json.return_value = {
            "tickets": [{"id": "t1", "status": "open"}, {"id": "t2", "status": "solved"}],
            "next_page": "https://next.example.com",
        }
        page2 = MagicMock()
        page2.status_code = 200
        page2.json.return_value = {"tickets": [{"id": "t3", "status": "new"}], "next_page": None}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            get = client.return_value.__aenter__.return_value.get
            get.side_effect = [page1, page2]
            tickets = await svc.get_tickets({
                "status": "open", "priority": "high", "assignee_id": "a1",
                "created_since": "2026-01-01", "limit": 500,
            })
        assert len(tickets) == 3
        assert svc.analytics_metrics["open_tickets"] == 2
        assert svc.analytics_metrics["closed_tickets"] == 1
        assert get.call_args_list[0].kwargs["params"]["per_page"] == 100

    async def test_api_error_returns_empty(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 401
        fake.text = "nope"
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            assert await svc.get_tickets() == []

    async def test_exception_returns_empty(self):
        svc = _svc()
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("x")):
            assert await svc.get_tickets() == []


class TestTicketInfoAndComments:
    async def test_get_ticket_info_circuit_breaker(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc:
                await svc.get_ticket_info("t-1")
        assert exc.value.status_code == 503

    async def test_get_ticket_info_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            from fastapi import HTTPException
            with pytest.raises(HTTPException) as exc:
                await svc.get_ticket_info("t-1")
        assert exc.value.status_code == 429

    async def test_get_ticket_info_success(self):
        svc = _svc()
        svc._get_ticket = AsyncMock(return_value={"id": "t-1"})
        assert await svc.get_ticket_info("t-1") == {"id": "t-1"}

    async def test_create_ticket_comment_success(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {"ticket": {"id": "t-1"}}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            put = client.return_value.__aenter__.return_value.put
            put.return_value = fake
            result = await svc.create_ticket_comment("t-1", "thanks")
        assert result["success"] is True
        assert put.call_args.kwargs["json"]["ticket"]["comment"]["public"] is True

    async def test_create_ticket_comment_api_error(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 400
        fake.text = "bad"
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.put.return_value = fake
            result = await svc.create_ticket_comment("t-1", "thanks")
        assert result["success"] is False

    async def test_create_ticket_comment_exception_generic(self):
        svc = _svc()
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("secret-internal-detail")):
            result = await svc.create_ticket_comment("t-1", "thanks")
        assert result["success"] is False
        assert "secret-internal-detail" not in result["error"]

    async def test_create_ticket_comment_circuit_breaker(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            result = await svc.create_ticket_comment("t-1", "thanks")
        assert result["success"] is False
        assert "temporarily disabled" in result["error"]

    async def test_create_ticket_comment_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            result = await svc.create_ticket_comment("t-1", "thanks")
        assert result["success"] is False
        assert "Rate limit" in result["error"]


class TestSupportAnalytics:
    async def test_generate_all_analytics_types(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai_response = MagicMock()
            ai_response.ok = True
            ai_response.output_data = {"insights": ["x"], "recommendations": ["y"]}
            ai.process_ai_request = AsyncMock(return_value=ai_response)
            svc = mod.AtomZendeskIntegrationService(
                config=_zd_config(ai_response_suggestions=True, ai_service=ai))
            tickets = [
                {"id": "t1", "status": "open", "priority": "high", "type": "incident",
                 "response_time": 100, "resolution_time": 500,
                 "satisfaction_rating": 5.0, "assignee_id": "a1",
                 "escalated": True, "resolved_first_contact": True},
                {"id": "t2", "status": "solved", "priority": "normal", "type": "question",
                 "response_time": 400, "resolution_time": 2000,
                 "satisfaction_rating": 3.0, "assignee_id": "a2",
                 "escalated": False, "resolved_first_contact": False},
            ]
            svc.get_tickets = AsyncMock(return_value=tickets)
            for atype in [
                mod.SupportAnalyticsType.RESPONSE_TIME,
                mod.SupportAnalyticsType.RESOLUTION_TIME,
                mod.SupportAnalyticsType.CUSTOMER_SATISFACTION,
                mod.SupportAnalyticsType.TICKET_VOLUME,
                mod.SupportAnalyticsType.AGENT_PERFORMANCE,
                mod.SupportAnalyticsType.ESCALATION_RATE,
                mod.SupportAnalyticsType.FIRST_CONTACT_RESOLUTION,
            ]:
                result = await svc.generate_support_analytics(atype, "7d")
                assert result["success"] is True
                assert result["analytics"]["analytics_type"] == atype
            ai.process_ai_request.assert_awaited()
            assert svc.performance_metrics["analytics_generation_time"] >= 0
        finally:
            importlib.reload(zdmod)

    async def test_generate_unsupported_type(self):
        svc = _svc()
        svc.get_tickets = AsyncMock(return_value=[])
        result = await svc.generate_support_analytics("BOGUS", "7d")
        assert result["success"] is True
        assert result["analytics"]["metrics"]["error"] == "Unsupported analytics type"

    async def test_generate_analytics_exception_generic(self):
        svc = _svc()
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("secret-internal-detail"))
        result = await svc.generate_support_analytics(
            zdmod.SupportAnalyticsType.TICKET_VOLUME, "7d")
        assert result["success"] is False
        assert "secret-internal-detail" not in result["error"]

    async def test_generate_circuit_breaker(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            result = await svc.generate_support_analytics(zdmod.SupportAnalyticsType.TICKET_VOLUME)
        assert result["success"] is False

    async def test_generate_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            result = await svc.generate_support_analytics(zdmod.SupportAnalyticsType.TICKET_VOLUME)
        assert result["success"] is False

    async def test_response_time_analytics(self):
        svc = _svc()
        data = await svc._generate_response_time_analytics([
            {"response_time": 100}, {"response_time": None}, {"id": "no-field"}])
        assert data["average_response_time"] == 100.0
        assert data["tickets_measured"] == 1
        assert data["insights"] == ["Response times within SLA"]
        data = await svc._generate_response_time_analytics([{"response_time": 500}])
        assert data["insights"] == ["Response times exceeding SLA"]
        assert data["recommendations"]
        data = await svc._generate_response_time_analytics([])
        assert data["average_response_time"] == 0.0

    async def test_resolution_time_analytics(self):
        svc = _svc()
        data = await svc._generate_resolution_time_analytics([{"resolution_time": 100}])
        assert data["insights"] == ["Resolution time stable"]
        data = await svc._generate_resolution_time_analytics([{"resolution_time": 2000}])
        assert data["insights"] == ["Resolution time rising"]
        data = await svc._generate_resolution_time_analytics([])
        assert data["average_resolution_time"] == 0.0

    async def test_satisfaction_analytics(self):
        svc = _svc()
        data = await svc._generate_satisfaction_analytics([
            {"satisfaction_rating": 5.0}, {"satisfaction_rating": "4"},
            {"satisfaction_rating": "not-a-number"}, {"id": "x"}])
        assert data["ratings_count"] == 2
        assert data["average_satisfaction"] == 4.5
        data = await svc._generate_satisfaction_analytics([])
        assert data["ratings_count"] == 0

    async def test_satisfaction_rating_zero_is_counted(self):
        svc = _svc()
        data = await svc._generate_satisfaction_analytics([
            {"satisfaction_rating": 0.0}, {"satisfaction_rating": 5.0}])
        assert data["ratings_count"] == 2
        assert data["average_satisfaction"] == 2.5

    async def test_volume_analytics(self):
        svc = _svc()
        data = await svc._generate_volume_analytics([
            {"priority": "high", "type": "incident"}, {"priority": "high"}])
        assert data["total_tickets"] == 2
        assert data["tickets_by_priority"]["high"] == 2
        assert data["tickets_by_type"]["question"] == 1
        assert data["insights"] == ["2 tickets in period"]
        data = await svc._generate_volume_analytics([])
        assert data["insights"] == ["No tickets in period"]

    async def test_agent_performance_analytics(self):
        svc = _svc()
        data = await svc._generate_agent_performance_analytics([
            {"assignee_id": "a1"}, {"assignee_id": "a1"}, {}])
        assert data["tickets_by_agent"]["a1"] == 2
        assert data["tickets_by_agent"]["unassigned"] == 1
        assert data["agent_count"] == 2
        data = await svc._generate_agent_performance_analytics([])
        assert data["agent_count"] == 0

    async def test_escalation_analytics(self):
        svc = _svc()
        data = await svc._generate_escalation_analytics([
            {"escalated": True}, {"escalated": False}])
        assert data["escalation_rate"] == 50.0
        assert data["insights"] == ["Escalation rate above target"]
        data = await svc._generate_escalation_analytics([{"escalated": False}])
        assert data["insights"] == ["Escalation rate normal"]
        data = await svc._generate_escalation_analytics([])
        assert data["escalation_rate"] == 0.0

    async def test_fcr_analytics(self):
        svc = _svc()
        data = await svc._generate_fcr_analytics([
            {"resolved_first_contact": True}, {"resolved_first_contact": True}])
        assert data["first_contact_resolution_rate"] == 100.0
        assert data["insights"] == ["FCR above target"]
        data = await svc._generate_fcr_analytics([{"resolved_first_contact": False}])
        assert data["insights"] == ["FCR below target"]
        assert data["recommendations"]
        data = await svc._generate_fcr_analytics([])
        assert data["first_contact_resolution_rate"] == 0.0


class TestAiInsights:
    async def test_ai_insights_success(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai_response = MagicMock()
            ai_response.ok = True
            ai_response.output_data = {"insights": ["deep"], "recommendations": ["act"]}
            ai.process_ai_request = AsyncMock(return_value=ai_response)
            svc = mod.AtomZendeskIntegrationService(config=_zd_config(ai_service=ai))
            out = await svc._generate_ai_insights({"avg": 1}, [])
            assert out["insights"] == ["deep"]
            ai_response.ok = False
            out = await svc._generate_ai_insights({"avg": 1}, [])
            assert out == {"insights": [], "recommendations": []}
        finally:
            importlib.reload(zdmod)

    async def test_ai_insights_no_service(self):
        svc = _svc()
        with patch.object(zdmod, "ai_enhanced_service", None):
            bare = zdmod.AtomZendeskIntegrationService(config=_zd_config())
            out = await bare._generate_ai_insights({"avg": 1}, [])
        assert out == {"insights": [], "recommendations": []}

    async def test_ai_insights_exception(self):
        mod = importlib.import_module("integrations.atom_zendesk_integration_service")
        stubs = {}
        for name, attrs in {
            "ai_enhanced_service": ["ai_enhanced_service", "AIModelType", "AIRequest", "AIResponse", "AIServiceType", "AITaskType"],
            "atom_ai_integration": ["atom_ai_integration"],
        }.items():
            m = MagicMock()
            for attr in attrs:
                setattr(m, attr, MagicMock())
            stubs[name] = m
        with patch.dict(sys.modules, stubs):
            importlib.reload(mod)
        try:
            ai = MagicMock()
            ai.process_ai_request = AsyncMock(side_effect=RuntimeError("x"))
            svc = mod.AtomZendeskIntegrationService(config=_zd_config(ai_service=ai))
            out = await svc._generate_ai_insights({"avg": 1}, [])
            assert out == {"insights": [], "recommendations": []}
        finally:
            importlib.reload(zdmod)


class TestAutoAssign:
    async def test_skill_match(self):
        svc = _svc()
        svc.agent_skills = {"agent-1": ["billing"], "agent-2": ["support"]}
        svc._get_available_agents = AsyncMock(return_value=[
            {"id": "agent-1"}, {"id": "agent-2"}])
        svc._get_agent_workload = AsyncMock(return_value=3)
        assignee = await svc._auto_assign_ticket({"suggested_agent_skills": ["billing"]})
        assert assignee == "agent-1"

    async def test_workload_too_high_falls_back(self):
        svc = _svc()
        svc.agent_skills = {"agent-1": ["billing"]}
        svc._get_available_agents = AsyncMock(return_value=[
            {"id": "agent-1"}, {"id": "agent-2"}])
        svc._get_agent_workload = AsyncMock(return_value=5)
        svc.analytics_metrics["agent_performance"]["agent-1"]["open_tickets"] = 9
        svc.analytics_metrics["agent_performance"]["agent-2"]["open_tickets"] = 1
        assignee = await svc._auto_assign_ticket({"suggested_agent_skills": ["billing"]})
        assert assignee == "agent-2"

    async def test_no_agents(self):
        svc = _svc()
        svc._get_available_agents = AsyncMock(return_value=[])
        assert await svc._auto_assign_ticket({}) is None

    async def test_exception_returns_none(self):
        svc = _svc()
        svc._get_available_agents = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._auto_assign_ticket({}) is None

    async def test_get_available_agents(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {
            "users": [{"id": "a1", "role": "agent"}, {"id": "e1", "role": "end-user"}]}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            agents = await svc._get_available_agents()
        assert agents == [{"id": "a1", "role": "agent"}]

    async def test_get_available_agents_error(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 403
        fake.text = "denied"
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            assert await svc._get_available_agents() == []

    async def test_get_available_agents_exception(self):
        svc = _svc()
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("x")):
            assert await svc._get_available_agents() == []

    async def test_get_agent_workload(self):
        svc = _svc()
        svc.get_tickets = AsyncMock(return_value=[{"id": "t1"}, {"id": "t2"}])
        assert await svc._get_agent_workload("a1") == 2

    async def test_get_agent_workload_exception(self):
        svc = _svc()
        svc.get_tickets = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._get_agent_workload("a1") == 0


class TestInternalHelpers:
    async def test_perform_security_check(self):
        with patch.object(zdmod, "atom_enterprise_security_service", None):
            svc = zdmod.AtomZendeskIntegrationService(config=_zd_config())
            assert await svc._perform_security_check({}) == {"passed": True, "reason": ""}
        svc = _svc(enable_enterprise_features=True)
        security = MagicMock()
        security.check = AsyncMock(return_value={"allowed": False, "reason": "nope"})
        svc.enterprise_security = security
        assert await svc._perform_security_check({}) == {"passed": False, "reason": "nope"}
        security.check = AsyncMock(return_value={"allowed": True})
        assert await svc._perform_security_check({}) == {"passed": True, "reason": ""}
        security.check = AsyncMock(side_effect=RuntimeError("x"))
        assert await svc._perform_security_check({}) == {"passed": True, "reason": ""}

    async def test_sync_ticket_to_salesforce(self):
        svc = _svc()
        await svc._sync_ticket_to_salesforce({"id": "t-1"})
        salesforce = MagicMock()
        salesforce.sync_ticket = AsyncMock()
        svc.salesforce_integration = salesforce
        await svc._sync_ticket_to_salesforce({"id": "t-1"})
        salesforce.sync_ticket.assert_awaited_once()
        salesforce.sync_ticket = AsyncMock(side_effect=RuntimeError("x"))
        await svc._sync_ticket_to_salesforce({"id": "t-1"})

    async def test_notify_platform_ticket_created(self):
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc = _svc()
        svc.platform_integrations["slack"] = integration
        await svc._notify_platform_ticket_created({"id": "t-1", "subject": "S"}, "slack")
        integration.send_notification.assert_awaited_once()
        integration.send_notification = AsyncMock(side_effect=RuntimeError("x"))
        await svc._notify_platform_ticket_created({"id": "t-1", "subject": "S"}, "slack")

    async def test_notify_platform_ticket_updated(self):
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc = _svc()
        svc.platform_integrations["slack"] = integration
        await svc._notify_platform_ticket_updated({"id": "t-1", "subject": "S"}, "slack")
        integration.send_notification.assert_awaited_once()
        integration.send_notification = AsyncMock(side_effect=RuntimeError("x"))
        await svc._notify_platform_ticket_updated({"id": "t-1", "subject": "S"}, "slack")

    async def test_sla_check_does_not_clobber_average_response_time(self):
        svc = _svc(sla_monitoring=True)
        svc.analytics_metrics["average_response_time"] = 42.0
        await svc._check_sla_compliance({"priority": "urgent"})
        assert svc.analytics_metrics["average_response_time"] == 42.0

    async def test_sla_check_unknown_priority_normalizes(self):
        svc = _svc(sla_monitoring=True)
        await svc._check_sla_compliance({"priority": "quantum"})
        await svc._check_sla_compliance({})

    async def test_sla_check_exception(self):
        svc = _svc(sla_monitoring=True)

        class BoomCfg:
            def __contains__(self, item):
                raise RuntimeError("x")

        svc.sla_config = BoomCfg()
        await svc._check_sla_compliance({"priority": "urgent"})

    async def test_check_escalation(self):
        svc = _svc(escalation_rules=True)
        await svc._check_escalation({"priority": "urgent"})
        await svc._check_escalation({"priority": "high"})
        await svc._check_escalation({"priority": "normal"})
        assert svc.analytics_metrics["escalation_rate"] == 2.0

    async def test_check_escalation_exception(self):
        svc = _svc(escalation_rules=True)

        class BoomTicket:
            def get(self, *args, **kwargs):
                raise RuntimeError("x")

        await svc._check_escalation(BoomTicket())

    async def test_trigger_ticket_workflows(self):
        with patch.object(zdmod, "atom_workflow_automation_service", None):
            bare = zdmod.AtomZendeskIntegrationService(config=_zd_config())
            await bare._trigger_ticket_workflows({"id": "t-1"}, "created")
        svc = _svc()
        automation = MagicMock()
        automation._handle_event_trigger = AsyncMock()
        svc.enterprise_automation = automation
        await svc._trigger_ticket_workflows({"id": "t-1"}, "created")
        automation._handle_event_trigger.assert_awaited_once()
        automation._handle_event_trigger = AsyncMock(side_effect=RuntimeError("x"))
        await svc._trigger_ticket_workflows({"id": "t-1"}, "created")

    async def test_cache_ticket(self):
        cache = MagicMock()
        cache.set = AsyncMock()
        svc = _svc(cache=cache)
        await svc._cache_ticket({"id": "t-1"})
        cache.set.assert_awaited_once()
        cache.set = AsyncMock(side_effect=RuntimeError("x"))
        await svc._cache_ticket({"id": "t-1"})

    async def test_get_ticket_cache_hit(self):
        cache = MagicMock()
        cache.get = AsyncMock(return_value={"id": "t-1"})
        svc = _svc(cache=cache)
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            assert await svc._get_ticket("t-1") == {"id": "t-1"}
        client.assert_not_called()

    async def test_get_ticket_api_fetch(self):
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock()
        svc = _svc(cache=cache)
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {"ticket": {"id": "t-1"}}
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            assert await svc._get_ticket("t-1") == {"id": "t-1"}
        cache.set.assert_awaited_once()

    async def test_get_ticket_api_not_found(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 404
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            assert await svc._get_ticket("t-1") is None

    async def test_get_ticket_exception(self):
        svc = _svc()
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient",
                   side_effect=RuntimeError("x")):
            assert await svc._get_ticket("t-1") is None

    async def test_test_zendesk_connection_success(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 200
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            assert await svc._test_zendesk_connection() is True

    async def test_test_zendesk_connection_failure(self):
        svc = _svc()
        fake = MagicMock()
        fake.status_code = 401
        with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
            client.return_value.__aenter__.return_value.get.return_value = fake
            with pytest.raises(Exception):
                await svc._test_zendesk_connection()

    async def test_initialize_salesforce_integration_import_error(self):
        sys.modules.pop("atom_salesforce_integration", None)
        svc = _svc()
        await svc._initialize_salesforce_integration()
        assert svc.salesforce_integration is None

    async def test_initialize_salesforce_integration_success(self):
        salesforce_mod = MagicMock()
        salesforce_mod.atom_salesforce_integration = MagicMock()
        with patch.dict(sys.modules, {"atom_salesforce_integration": salesforce_mod}):
            svc = _svc()
            await svc._initialize_salesforce_integration()
        assert svc.salesforce_integration is salesforce_mod.atom_salesforce_integration


class TestServiceStatusAndClose:
    async def test_get_service_status(self):
        svc = _svc()
        svc.is_initialized = True
        status = await svc.get_service_status()
        assert status["service"] == "zendesk_integration"
        assert status["status"] == "active"
        assert status["zendesk_config"]["subdomain"] == "test"

    async def test_get_service_status_error(self):
        svc = _svc()

        class Boom:
            def __getitem__(self, key):
                raise RuntimeError("secret-internal-detail")

        with patch.object(svc, "zendesk_config", Boom()):
            status = await svc.get_service_status()
        assert "error" in status
        assert "secret-internal-detail" not in status["error"]

    async def test_close_success(self):
        svc = _svc()
        await svc.close()

    async def test_close_circuit_breaker(self):
        svc = _svc()
        with patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=False)):
            await svc.close()

    async def test_close_rate_limited(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(True, 0))):
            await svc.close()

    async def test_close_exception(self):
        svc = _svc()
        with patch.object(zdmod.rate_limiter, "is_rate_limited", side_effect=RuntimeError("x")):
            await svc.close()


class TestAuditActionNames:
    async def test_audit_action_names(self):
        svc = _svc()
        svc._get_ticket = AsyncMock(return_value={"id": "t-1"})
        svc.get_tickets = AsyncMock(return_value=[])
        fake = MagicMock()
        fake.status_code = 200
        fake.json.return_value = {"ticket": {"id": "t-1"}}
        with patch("integrations.atom_zendesk_integration_service.log_integration_attempt") as attempt, \
             patch.object(zdmod.circuit_breaker, "is_enabled", new=AsyncMock(return_value=True)), \
             patch.object(zdmod.rate_limiter, "is_rate_limited", new=AsyncMock(return_value=(False, 99))):
            attempt.return_value = {"connector_id": "atom_zendesk_integration",
                                    "method": "create_ticket", "start_time": 0, "params": {}}
            with patch("integrations.atom_zendesk_integration_service.httpx.AsyncClient") as client:
                client.return_value.__aenter__.return_value.put.return_value = fake
                await svc.create_ticket(_ticket())
                await svc.update_ticket("t-1", {"status": "open"})
                await svc.get_ticket_info("t-1")
                await svc.create_ticket_comment("t-1", "hi")
                await svc.generate_support_analytics(zdmod.SupportAnalyticsType.TICKET_VOLUME)
                await svc.close()
        names = [call.args[1] for call in attempt.call_args_list]
        assert names == [
            "create_ticket", "update_ticket", "get_ticket_info",
            "create_ticket_comment", "generate_support_analytics", "close",
        ]
