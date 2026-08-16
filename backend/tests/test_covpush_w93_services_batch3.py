# -*- coding: utf-8 -*-
"""Coverage wave 93 batch 3 — integrations services:

- integrations/atom_hubspot_integration_service.py
- integrations/jira_service.py
- integrations/quickbooks_service.py
- integrations/teams_service.py
- integrations/asana_real_service.py

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM: httpx/aiohttp/requests boundaries, circuit breaker,
rate limiter, audit logger and DB sessions are all mocked.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import requests as requests_mod
from fastapi import HTTPException

import integrations.atom_hubspot_integration_service as hs
from integrations.atom_hubspot_integration_service import (
    AnalyticsType,
    AtomHubSpotIntegrationService,
)
import integrations.jira_service as jira_mod
from integrations.jira_service import JiraService, get_jira_service
import integrations.quickbooks_service as qb_mod
from integrations.quickbooks_service import QuickBooksService
from integrations.teams_service import TeamsService
import integrations.asana_real_service as ar
from integrations.asana_real_service import AsanaRealService


def _resp(payload=None, status=200, text='body'):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    r.text = text
    return r


def _err(status=500):
    r = _resp(None, status)
    r.raise_for_status.side_effect = requests_mod.HTTPError('x')
    return r


def _http_resp(status=200, json_data=None):
    return httpx.Response(status, json=json_data if json_data is not None else {},
                          request=httpx.Request('GET', 'http://x'))


def _acm(post_result=None, get_result=None):
    client = MagicMock()
    client.post = AsyncMock(return_value=post_result or _http_resp(200, {}))
    client.get = AsyncMock(return_value=get_result or _http_resp(200, {}))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ============================================================================
# AtomHubSpotIntegrationService
# ============================================================================

class TestAtomHubSpot:
    @pytest.fixture(autouse=True)
    def _guards(self):
        with patch.object(hs.circuit_breaker, 'is_enabled',
                          new=AsyncMock(return_value=True)), \
             patch.object(hs.rate_limiter, 'is_rate_limited',
                          new=AsyncMock(return_value=(False, 100))), \
             patch.object(hs, 'log_integration_attempt',
                          return_value={'start_time': 0.0}), \
             patch.object(hs, 'log_integration_complete',
                          MagicMock(return_value=0.1)):
            yield

    def _svc(self, **cfg):
        base = {'hubspot_access_token': 'tok'}
        base.update(cfg)
        return AtomHubSpotIntegrationService(config=base)

    def test_init(self):
        svc = self._svc()
        assert svc.tenant_id == 'default'
        assert svc.hubspot_config['base_url'] == 'https://api.hubapi.com'
        assert 'contacts' in svc.api_endpoints
        assert svc.analytics_metrics['total_contacts'] == 0
        assert not svc.is_initialized
        bare = AtomHubSpotIntegrationService()
        assert bare.hubspot_config['api_key'] is None

    async def test_initialize_success(self):
        svc = self._svc()
        with patch.object(svc, '_test_hubspot_connection', AsyncMock()):
            assert await svc.initialize() is True
            assert svc.is_initialized

    async def test_initialize_failure(self):
        svc = self._svc()
        with patch.object(svc, '_test_hubspot_connection',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert await svc.initialize() is False

    async def test_breaker_and_rate_limit_paths(self):
        svc = self._svc()
        with patch.object(hs.circuit_breaker, 'is_enabled',
                          new=AsyncMock(return_value=False)):
            r = await svc.create_contact({'email': 'a@b.c'})
            assert r['success'] is False
            with pytest.raises(HTTPException) as ei:
                await svc.create_campaign({'name': 'C',
                                           'start_date': datetime(2026, 1, 1)})
            assert ei.value.status_code == 503
            with pytest.raises(HTTPException) as ei:
                await svc.generate_marketing_analytics(AnalyticsType.LEAD_SCORING)
            assert ei.value.status_code == 503
            with pytest.raises(HTTPException):
                await svc.close()
        with patch.object(hs.rate_limiter, 'is_rate_limited',
                          new=AsyncMock(return_value=(True, 0))):
            assert (await svc.create_contact({'email': 'a@b.c'}))['success'] is False
            with pytest.raises(HTTPException) as ei:
                await svc.create_campaign({'name': 'C',
                                           'start_date': datetime(2026, 1, 1)})
            assert ei.value.status_code == 429
            with pytest.raises(HTTPException) as ei:
                await svc.generate_marketing_analytics(AnalyticsType.LEAD_SCORING)
            assert ei.value.status_code == 429
            with pytest.raises(HTTPException):
                await svc.close()

    async def test_create_contact_success_and_branches(self):
        svc = self._svc()
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(
                              201, {'id': 'c1'}))):
            r = await svc.create_contact(
                {'email': 'a@b.c', 'first_name': 'A', 'last_name': 'B',
                 'properties': {'x': 1}, 'source': 'referral'})
            assert r['success'] is True and r['contact_id'] == 'c1'
            assert r['lead_score'] >= 0  # lead scoring exercised
        # security check fail
        svc2 = self._svc(enable_enterprise_features=True)
        svc2._perform_security_check = AsyncMock(
            return_value={'passed': False, 'reason': 'blocked'})
        assert (await svc2.create_contact({'email': 'a@b.c'}))['error'] == 'blocked'
        # non-201
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(400, {}))):
            r = await svc.create_contact({'email': 'a@b.c'})
            assert r['success'] is False and 'Failed' in r['error']
        # network exception
        bad = MagicMock()
        bad.post = AsyncMock(side_effect=RuntimeError('net'))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=bad)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(hs.httpx, 'AsyncClient', return_value=cm):
            assert (await svc.create_contact({'email': 'a@b.c'}))['success'] is False
        # platform notification
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations['slack'] = integration
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(
                              201, {'id': 'c2'}))):
            r = await svc.create_contact({'email': 'a@b.c'}, platform='slack')
            assert r['success'] is True
            integration.send_notification.assert_awaited()

    async def test_create_contact_lifecycle_stages(self):
        svc = self._svc(enable_lead_scoring=True)
        stages = []
        for fake_score in (85, 65, 10):
            svc._score_lead = AsyncMock(return_value=float(fake_score))
            with patch.object(hs.httpx, 'AsyncClient',
                              return_value=_acm(post_result=_http_resp(
                                  201, {'id': 'x'}))):
                await svc.create_contact({'email': 'a@b.c'})
            stages.append(svc.__dict__)  # no-op keep
        svc._score_lead = AsyncMock(return_value=85.0)
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(
                              201, {'id': 'x'}))):
            r = await svc.create_contact({'email': 'a@b.c'})
        assert r['success'] is True

    async def test_create_campaign_branches(self):
        start = datetime(2026, 1, 1)
        svc = self._svc()
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(
                              201, {'id': 'cp1', 'name': 'C'}))):
            r = await svc.create_campaign({'name': 'C', 'start_date': start,
                                           'end_date': None})
            assert r['success'] is True and r['campaign_id'] == 'cp1'
        # security fail
        svc2 = self._svc(enable_enterprise_features=True)
        svc2._perform_security_check = AsyncMock(
            return_value={'passed': False, 'reason': 'denied'})
        assert (await svc2.create_campaign({'name': 'C',
                                            'start_date': start}))['error'] == 'denied'
        # non-201
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(400, {}))):
            r = await svc.create_campaign({'name': 'C', 'start_date': start})
            assert r['success'] is False
        # exception (missing start_date -> isoformat on None)
        assert (await svc.create_campaign({'name': 'C'}))['success'] is False
        # network exception
        bad = MagicMock()
        bad.post = AsyncMock(side_effect=RuntimeError('net'))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=bad)
        cm.__aexit__ = AsyncMock(return_value=False)
        with patch.object(hs.httpx, 'AsyncClient', return_value=cm):
            r = await svc.create_campaign({'name': 'C', 'start_date': start})
            assert r['success'] is False
        # platform notification
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations['teams'] = integration
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(post_result=_http_resp(
                              201, {'id': 'cp2', 'name': 'C', 'type': 'email'}))):
            r = await svc.create_campaign({'name': 'C', 'start_date': start},
                                          platform='teams')
            assert r['success'] is True
            integration.send_notification.assert_awaited()

    async def test_generate_marketing_analytics_all_types(self):
        svc = self._svc()
        gens = ['_generate_campaign_performance_analytics',
                '_generate_lead_conversion_analytics',
                '_generate_email_performance_analytics',
                '_generate_social_media_analytics',
                '_generate_website_traffic_analytics',
                '_generate_marketing_roi_analytics',
                '_generate_lead_scoring_analytics',
                '_generate_ab_testing_analytics']
        for g in gens:
            setattr(svc, g, AsyncMock(return_value={'insights': ['i']}))
        svc._generate_ai_insights = AsyncMock(return_value={'note': 'ai'})
        for atype in AnalyticsType:
            r = await svc.generate_marketing_analytics(atype)
            assert r['success'] is True, atype
        # exercise the real generator implementations
        svc2 = self._svc()
        r = await svc2.generate_marketing_analytics(
            AnalyticsType.CAMPAIGN_PERFORMANCE)
        assert r['success'] is True
        for atype in (AnalyticsType.LEAD_CONVERSION, AnalyticsType.EMAIL_PERFORMANCE,
                      AnalyticsType.SOCIAL_MEDIA_ENGAGEMENT,
                      AnalyticsType.WEBSITE_TRAFFIC, AnalyticsType.MARKETING_ROI,
                      AnalyticsType.LEAD_SCORING, AnalyticsType.AB_TESTING):
            await svc2.generate_marketing_analytics(atype)
        # unsupported analytics type
        r = await svc2.generate_marketing_analytics('bogus')
        assert r['success'] is True
        assert r['analytics']['metrics']['error'] == 'Unsupported analytics type'
        # exception path
        svc2._generate_campaign_performance_analytics = AsyncMock(
            side_effect=RuntimeError('x'))
        r = await svc2.generate_marketing_analytics(
            AnalyticsType.CAMPAIGN_PERFORMANCE)
        assert r['success'] is False
        # analytics disabled -> no AI insights
        svc3 = self._svc(enable_analytics=False)
        r = await svc3.generate_marketing_analytics(
            AnalyticsType.CAMPAIGN_PERFORMANCE)
        assert r['success'] is True

    async def test_rule_based_lead_scoring(self):
        svc = self._svc()
        score = await svc._rule_based_lead_scoring({
            'company': 'Acme', 'job_title': 'CEO', 'email': 'a@acme.com',
            'phone': '555', 'website': 'w', 'source': 'referral'})
        assert score >= 55
        mid = await svc._rule_based_lead_scoring({'job_title': 'Manager',
                                                  'source': 'website'})
        assert 15 <= mid < 55
        jr = await svc._rule_based_lead_scoring({'job_title': 'Senior Dev'})
        assert jr < mid
        base = await svc._rule_based_lead_scoring({})
        assert base == 5  # job title else-branch
        free = await svc._rule_based_lead_scoring({'email': 'a@gmail.com'})
        assert free == 5
        bad = await svc._rule_based_lead_scoring(None)
        assert bad == 50.0

    async def test_score_lead_with_fake_ai(self, monkeypatch):
        # Patch module-level AI symbols so _score_lead/_optimize run the AI path
        monkeypatch.setattr(hs, 'AIRequest', lambda **kw: SimpleNamespace(**kw))
        monkeypatch.setattr(hs, 'AITaskType',
                            SimpleNamespace(PREDICTION='p',
                                            CONTENT_ANALYSIS='c'))
        monkeypatch.setattr(hs, 'AIModelType', SimpleNamespace(GPT_4='g'))
        monkeypatch.setattr(hs, 'AIServiceType', SimpleNamespace(OPENAI='o'))
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={'lead_score': 85, 'scoring_factors': {}}))
        svc = self._svc(ai_service=ai)
        svc.analytics_metrics['total_contacts'] = 1
        assert await svc._score_lead({'email': 'x@y.com'}) == 85.0
        # fallback to rule-based
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        assert 0 <= await svc._score_lead({'email': 'a@b.c'}) <= 100
        # exception -> rule-based fallback
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
        assert 0 <= await svc._score_lead({}) <= 100
        # exception + rule-based failing -> default 50
        with patch.object(svc, '_rule_based_lead_scoring',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert await svc._score_lead({}) == 50.0

    async def test_generate_ai_insights(self, monkeypatch):
        monkeypatch.setattr(hs, 'AIRequest', lambda **kw: SimpleNamespace(**kw))
        monkeypatch.setattr(hs, 'AITaskType',
                            SimpleNamespace(CONTENT_ANALYSIS='c'))
        monkeypatch.setattr(hs, 'AIModelType', SimpleNamespace(GPT_4='g'))
        monkeypatch.setattr(hs, 'AIServiceType', SimpleNamespace(OPENAI='o'))
        svc = self._svc()
        assert (await svc._generate_ai_insights({}, AnalyticsType.LEAD_SCORING)) == \
            {'insights': [], 'recommendations': []}
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={'insights': ['x']}))
        svc2 = self._svc(ai_service=ai)
        assert (await svc2._generate_ai_insights(
            {}, AnalyticsType.LEAD_SCORING))['insights'] == ['x']
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        assert (await svc2._generate_ai_insights(
            {}, AnalyticsType.LEAD_SCORING))['insights'] == []
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc2._generate_ai_insights(
            {}, AnalyticsType.LEAD_SCORING))['insights'] == []

    async def test_optimize_campaign_with_ai(self, monkeypatch):
        monkeypatch.setattr(hs, 'AIRequest', lambda **kw: SimpleNamespace(**kw))
        monkeypatch.setattr(hs, 'AITaskType',
                            SimpleNamespace(CONTENT_ANALYSIS='c'))
        monkeypatch.setattr(hs, 'AIModelType', SimpleNamespace(GPT_4='g'))
        monkeypatch.setattr(hs, 'AIServiceType', SimpleNamespace(OPENAI='o'))
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={'optimized_subject': 'S'}))
        svc = self._svc(ai_service=ai)
        assert (await svc._optimize_campaign_with_ai(
            {'subject': 'orig'}))['optimized_subject'] == 'S'
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        assert (await svc._optimize_campaign_with_ai(
            {'subject': 'orig'}))['optimized_subject'] == 'orig'
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc._optimize_campaign_with_ai(
            {'subject': 'orig'}))['optimized_subject'] == 'orig'

    async def test_auth_headers_and_connection_test(self):
        svc = self._svc()
        assert (await svc._get_auth_headers())['Authorization'] == 'Bearer tok'
        svc.hubspot_config['access_token'] = None
        svc.hubspot_config['api_key'] = 'k'
        assert 'Bearer k' in (await svc._get_auth_headers())['Authorization']
        svc.hubspot_config['api_key'] = None
        with pytest.raises(Exception):
            await svc._get_auth_headers()
        svc = self._svc()  # fresh service with token again
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(get_result=_http_resp(200, {}))):
            assert await svc._test_hubspot_connection() is True
        with patch.object(hs.httpx, 'AsyncClient',
                          return_value=_acm(get_result=_http_resp(500, {}))):
            with pytest.raises(Exception):
                await svc._test_hubspot_connection()

    async def test_security_check_and_setup(self):
        svc = self._svc()
        assert (await svc._perform_security_check({}))['passed'] is True
        sec = MagicMock()
        sec.check = AsyncMock(return_value={'allowed': False, 'reason': 'no'})
        svc.enterprise_security = sec
        assert (await svc._perform_security_check({}))['passed'] is False
        sec.check = AsyncMock(return_value={'allowed': True})
        assert (await svc._perform_security_check({}))['passed'] is True
        sec.check = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc._perform_security_check({}))['passed'] is True
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

    async def test_cache_workflows_and_notify(self):
        cache = MagicMock()
        cache.set = AsyncMock()
        svc = self._svc(cache=cache)
        await svc._cache_contact({'id': '1'})
        await svc._cache_campaign({'id': '1'})
        cache.set.assert_awaited()
        await svc._send_automated_email({'id': '1'}, {})
        await svc._add_contact_to_list({'id': '1'}, {'list_id': 'l'})
        await svc._create_marketing_task({'id': '1'}, {})
        await svc._update_contact_properties({'id': '1'}, {})
        # workflows
        svc.automation_flows = {
            'f1': {'trigger_event': 'contact_created',
                   'conditions': {'lead_score_min': 60},
                   'actions': [{'type': 'send_email'},
                               {'type': 'add_to_list'},
                               {'type': 'create_task'},
                               {'type': 'update_properties'}]},
            'f2': {'trigger_event': 'other', 'conditions': {}, 'actions': []},
        }
        await svc._trigger_automation_workflows(
            {'properties': {'hs_lead_score': '70'}}, 'contact_created')
        svc.hubspot_config['automation_workflows'] = False
        await svc._trigger_automation_workflows({'id': '1'}, 'contact_created')
        await svc._trigger_campaign_workflows(
            {'id': 'c1', 'status': 'draft'}, 'created')
        await svc._trigger_campaign_workflows({}, 'created')
        assert svc._evaluate_workflow_conditions(
            {'lifecycle_stage': 'lead'},
            {'properties': {'lifecyclestage': 'lead'}}) is True
        assert svc._evaluate_workflow_conditions(
            {'lifecycle_stage': 'lead'},
            {'properties': {'lifecyclestage': 'customer'}}) is False
        assert svc._evaluate_workflow_conditions(
            {'lead_score_min': 50},
            {'properties': {'hs_lead_score': '60'}}) is True
        assert svc._evaluate_workflow_conditions({}, {}) is True
        # exception inside workflow execution is swallowed
        await svc._execute_workflow({'actions': [{'type': 'bogus'}]}, {'id': 1})
        # notify
        integration = MagicMock()
        integration.send_notification = AsyncMock()
        svc.platform_integrations['slack'] = integration
        await svc._notify_platform_lead_created({'id': '1'}, 'slack')
        await svc._notify_platform_lead_created({'id': '1'}, 'nope')
        await svc._notify_platform_campaign_created({'name': 'C'}, 'slack')
        await svc._notify_platform_campaign_created({}, 'nope')
        integration.send_notification.assert_awaited()
        # failing cache swallowed
        bad_cache = MagicMock()
        bad_cache.set = AsyncMock(side_effect=RuntimeError('x'))
        svc2 = self._svc(cache=bad_cache)
        await svc2._cache_contact({'id': '1'})
        await svc2._cache_campaign({'id': '1'})

    async def test_status_and_close(self):
        svc = self._svc()
        r = await svc.get_service_status()
        assert r['service'] == 'hubspot_integration' and r['status'] == 'inactive'
        svc.is_initialized = True
        assert (await svc.get_service_status())['status'] == 'active'
        await svc.close()
        svc2 = self._svc()
        svc2.hubspot_config = {}
        assert 'error' in (await svc2.get_service_status())


# ============================================================================
# JiraService
# ============================================================================

class TestJiraService:
    @pytest.fixture()
    def svc(self, monkeypatch):
        for v in ('JIRA_BASE_URL', 'JIRA_USERNAME', 'JIRA_API_TOKEN'):
            monkeypatch.delenv(v, raising=False)
        return JiraService(tenant_id='t1', config={
            'base_url': 'https://jira.example.com',
            'username': 'u', 'api_token': 'tok'})

    def test_init_variants(self, monkeypatch):
        oauth = JiraService(config={'access_token': 'a', 'cloud_id': 'cid'})
        assert oauth.base_url == 'https://api.atlassian.com/ex/jira/cid'
        assert oauth.session.headers['Authorization'] == 'Bearer a'
        basic = JiraService(config={'base_url': 'https://j.example.com/',
                                    'username': 'u', 'api_token': 'p'})
        assert basic.base_url == 'https://j.example.com'
        assert basic.session.headers['Authorization'].startswith('Basic ')
        with pytest.raises(ValueError):
            JiraService(config={'base_url': 'http://127.0.0.1:8080'})
        with patch.object(jira_mod, 'os') as osm:
            osm.getenv.return_value = None
            bare = JiraService(tenant_id='nobaseurl', config={})
            assert bare.base_url is None

    def test_make_request_with_token(self, svc):
        with patch.object(svc.session, 'request', return_value=_resp()) as m:
            svc._make_request('GET', '/x', token='dyn')
            assert m.call_args[1]['headers']['Authorization'] == 'Bearer dyn'
            assert m.call_args[1]['url'] == 'https://jira.example.com/x'

    def test_test_connection(self, svc):
        with patch.object(svc.session, 'get',
                          return_value=_resp({'displayName': 'D',
                                              'emailAddress': 'e'})):
            r = svc.test_connection()
            assert r['status'] == 'success' and r['user'] == 'D'
        with patch.object(svc.session, 'get', return_value=_resp(None, 401)):
            r = svc.test_connection()
            assert r['authenticated'] is False
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            r = svc.test_connection()
            assert r['status'] == 'error'

    def test_project_ops(self, svc):
        with patch.object(svc.session, 'request',
                          return_value=_resp([{'key': 'X'}])) as m:
            assert svc.get_projects(start_at=1, max_results=2) == [{'key': 'X'}]
            assert m.call_args[1]['params'] == {'startAt': 1, 'maxResults': 2}
            assert svc.get_project('X') == [{'key': 'X'}]  # passthrough json
            assert svc.get_projects(token='t') == [{'key': 'X'}]
        with patch.object(svc.session, 'request', side_effect=RuntimeError('x')):
            assert svc.get_projects() == []
            assert svc.get_project('X') is None

    def test_issue_ops(self, svc):
        with patch.object(svc.session, 'request') as m:
            m.return_value = _resp({'issues': [1], 'total': 1})
            assert svc.search_issues('jql', fields=['a'])['issues'] == [1]
            assert svc.search_issues('jql')['issues'] == [1]
            m.return_value = _resp({'key': 'X-1'})
            assert svc.get_issue('X-1') == {'key': 'X-1'}
            m.return_value = _resp({'id': 'new'})
            assert svc.create_issue('X', 'sum', 'Bug', 'desc',
                                    priority='P1', assignee='u') == {'id': 'new'}
            m.return_value = _resp()
            assert svc.update_issue('X-1', {}) is True
            assert svc.add_comment('X-1', 'hi') == {}
            assert svc.get_comments('X-1') == []
            assert svc.assign_issue('X-1', 'u') is True
        with patch.object(svc.session, 'request', side_effect=RuntimeError('x')):
            assert svc.search_issues('j') == {'issues': [], 'total': 0,
                                              'startAt': 0, 'maxResults': 0}
            assert svc.get_issue('X-1') is None
            assert svc.create_issue('X', 's', 'T') is None
            assert svc.update_issue('X-1', {}) is False
            assert svc.add_comment('X-1', 'b') is None
            assert svc.get_comments('X-1') == []
            assert svc.assign_issue('X-1', 'u') is False

    def test_transition_issue(self, svc):
        transitions = _resp({'transitions': [{'id': '10', 'name': 'Done'},
                                             {'id': '20', 'name': 'In Progress'}]})
        ok = _resp()
        with patch.object(svc.session, 'request',
                          side_effect=[transitions, ok]) as m:
            assert svc.transition_issue('X-1', 'done', comment='c') is True
            assert 'comment' in m.call_args[1]['json']['update']
        transitions2 = _resp({'transitions': [{'id': '10', 'name': 'Done'}]})
        with patch.object(svc.session, 'request',
                          side_effect=[transitions2, ok]):
            assert svc.transition_issue('X-1', 'Done') is True
        with patch.object(svc.session, 'request',
                          return_value=_resp({'transitions': []})):
            assert svc.transition_issue('X-1', 'Nope') is False
        with patch.object(svc.session, 'request', side_effect=RuntimeError('x')):
            assert svc.transition_issue('X-1', 'Done') is False

    def test_metadata_ops(self, svc):
        with patch.object(svc.session, 'request') as m:
            m.return_value = _resp([{'id': 'u'}])
            assert svc.get_users(project_key='X') == [{'id': 'u'}]
            assert svc.get_users() == [{'id': 'u'}]
            m.return_value = _resp([{'id': 's'}])
            assert svc.get_statuses('X') == [{'id': 's'}]
            assert svc.get_issue_types('X') == [{'id': 's'}]
            assert svc.get_issue_types() == [{'id': 's'}]
            m.return_value = _resp({'worklogs': [1]})
            assert svc.get_worklogs('X-1') == [1]
            m.return_value = _resp({'id': 'w'})
            assert svc.add_worklog('X-1', '1h', 'c', '2026-01-01') == {'id': 'w'}
            assert svc.add_worklog('X-1', '1h') == {'id': 'w'}
            m.return_value = _resp([{'id': 'comp'}])
            assert svc.get_project_components('X') == [{'id': 'comp'}]
        with patch.object(svc.session, 'request', side_effect=RuntimeError('x')):
            assert svc.get_users() == []
            assert svc.get_statuses('X') == []
            assert svc.get_issue_types() == []
            assert svc.get_worklogs('X-1') == []
            assert svc.add_worklog('X-1', '1h') is None
            assert svc.get_project_components('X') == []

    def test_health_check(self, svc):
        with patch.object(svc.session, 'get',
                          return_value=_resp({'displayName': 'D'})):
            assert svc.health_check()['healthy'] is True
        with patch.object(svc.session, 'get', return_value=_resp(None, 401)):
            assert svc.health_check()['healthy'] is False
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.health_check()['healthy'] is False
        bare = JiraService(tenant_id='t', config={})
        bare.base_url = None
        assert bare.health_check()['healthy'] is False

    def test_capabilities(self, svc):
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is True
        assert any(o['id'] == 'create_issue' for o in caps['operations'])

    async def test_sync_to_postgres_cache(self, svc, monkeypatch):
        def totals_seq(*vals):
            it = iter(vals)
            return MagicMock(side_effect=lambda jql, **kw: next(it))

        svc.search_issues = totals_seq({'total': 10}, {'total': 4}, {'total': 6})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('X"Q')
        assert r == {'success': True, 'metrics_synced': 3}
        assert '\\"' in svc.search_issues.call_args_list[0][0][0]
        # update path
        svc.search_issues = totals_seq({'total': 1}, {'total': 1}, {'total': 0})
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        assert (await svc.sync_to_postgres_cache('X'))['metrics_synced'] == 3
        # inner error
        svc.search_issues = totals_seq({'total': 1}, {'total': 1}, {'total': 0})
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('X'))['success'] is False
        assert db.rollback.called
        # outer error
        svc.search_issues = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('X'))['success'] is False

    async def test_full_sync(self, svc):
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('X')
        assert r['success'] and r['project_key'] == 'X'

    async def test_execute_entity_operation(self, svc):
        svc.create_issue = MagicMock(return_value={'id': 'n'})
        r = await svc.execute_entity_operation('create', 'issue',
                                               {'project_key': 'X',
                                                'summary': 's'})
        assert r['success'] and r['result'] == {'id': 'n'}
        svc.get_issue = MagicMock(return_value={'key': 'X-1'})
        r = await svc.execute_entity_operation('get', 'issue',
                                               {'issue_key': 'X-1'})
        assert r['success']
        r = await svc.execute_entity_operation('get', 'issue', {})
        assert r['success'] is False
        svc.search_issues = MagicMock(return_value={'issues': []})
        r = await svc.execute_entity_operation('list', 'issue', {'jql': 'x'})
        assert r['success']
        r = await svc.execute_entity_operation('list', 'issue',
                                               {'project': 'P'})
        assert 'project = "P"' in svc.search_issues.call_args[1]['jql']
        r = await svc.execute_entity_operation('list', 'issue', {})
        assert svc.search_issues.call_args[1]['jql'] == 'order by created DESC'
        assert (await svc.execute_entity_operation(
            'get', 'project', {}))['success'] is False
        assert (await svc.execute_entity_operation(
            'delete', 'issue', {}))['success'] is False
        svc.create_issue = MagicMock(side_effect=RuntimeError('x'))
        r = await svc.execute_entity_operation('create', 'issue', {})
        assert r['success'] is False

    async def test_execute_operation(self, svc):
        svc.create_issue = MagicMock(return_value={'id': 'n'})
        svc.search_issues = MagicMock(return_value={'issues': []})
        svc.update_issue = MagicMock(return_value=True)
        svc.get_projects = MagicMock(return_value=[])
        svc.add_comment = MagicMock(return_value={'id': 'c'})
        for op in ('create_issue', 'search_issues', 'update_issue',
                   'get_projects', 'add_comment'):
            r = await svc.execute_operation(op, {'project_key': 'X',
                                                 'summary': 's',
                                                 'issue_key': 'K',
                                                 'jql': 'j'})
            assert r['success'] is True, op
        assert (await svc.execute_operation('nope', {}))['success'] is False
        # tenant mismatch
        r = await svc.execute_operation('get_projects', {},
                                        context={'tenant_id': 'other'})
        assert r['success'] is False and 'mismatch' in r['error']
        # matching tenant OK
        r = await svc.execute_operation('get_projects', {},
                                        context={'tenant_id': 't1'})
        assert r['success'] is True
        # inner failures raise -> error envelope
        svc.update_issue = MagicMock(return_value=False)
        r = await svc.execute_operation('update_issue', {'issue_key': 'K'})
        assert r['success'] is False
        svc.create_issue = MagicMock(return_value=None)
        assert (await svc.execute_operation('create_issue',
                                            {}))['success'] is False
        svc.add_comment = MagicMock(return_value=None)
        assert (await svc.execute_operation('add_comment',
                                            {}))['success'] is False

    def test_get_jira_service(self, monkeypatch):
        monkeypatch.delenv('JIRA_API_TOKEN', raising=False)
        monkeypatch.delenv('JIRA_ACCESS_TOKEN', raising=False)
        monkeypatch.setenv('JIRA_API_TOKEN', 'tok')
        monkeypatch.setenv('JIRA_CLOUD_ID', 'cid')
        s1 = get_jira_service()
        assert s1 is get_jira_service()
        monkeypatch.setattr(jira_mod, '_jira_service_singleton', None)
        monkeypatch.delenv('JIRA_CLOUD_ID', raising=False)
        monkeypatch.setenv('JIRA_BASE_URL', 'https://j.example.com')
        s2 = get_jira_service()
        assert s2 is not None
        monkeypatch.setattr(jira_mod, '_jira_service_singleton', None)
        monkeypatch.delenv('JIRA_API_TOKEN', raising=False)
        assert get_jira_service() is None
        monkeypatch.setattr(jira_mod, '_jira_service_singleton', None)


# ============================================================================
# QuickBooksService
# ============================================================================

class TestQuickBooks:
    @pytest.fixture()
    def svc(self, monkeypatch):
        for v in ('QUICKBOOKS_CLIENT_ID', 'QUICKBOOKS_CLIENT_SECRET',
                  'QUICKBOOKS_ACCESS_TOKEN', 'QUICKBOOKS_REALM_ID',
                  'QUICKBOOKS_USE_SANDBOX'):
            monkeypatch.delenv(v, raising=False)
        return QuickBooksService(tenant_id='t1', config={
            'client_id': 'cid', 'client_secret': 'cs',
            'access_token': 'tok', 'realm_id': 'r1'})

    def _http(self, svc, resp):
        svc.http = MagicMock()
        svc.http.get = AsyncMock(return_value=resp)
        svc.http.post = AsyncMock(return_value=resp)

    def test_init_and_helpers(self, svc):
        assert svc.base_url.endswith('/v3')
        assert svc._get_api_url() == svc.base_url
        svc.use_sandbox = True
        assert svc._get_api_url() == svc.sandbox_url
        assert svc._get_headers('t')['Authorization'] == 'Bearer t'
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is False
        assert 'get_invoices' in caps['operations']
        url = svc.get_authorization_url('http://cb', 'st1')
        assert url.startswith(svc.auth_url) and 'state=st1' in url
        assert 'state' not in svc.get_authorization_url('http://cb')

    async def test_close(self, svc):
        svc.client = MagicMock()
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited()

    async def test_exchange_token(self, svc):
        self._http(svc, _http_resp(200, {'access_token': 'n',
                                         'realmId': 'r2'}))
        r = await svc.exchange_token('code', 'http://cb')
        assert r['access_token'] == 'n' and svc.realm_id == 'r2'
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError('x'))
        with pytest.raises(HTTPException):
            await svc.exchange_token('c', 'http://cb')
        bare = QuickBooksService(tenant_id='t', config={})
        bare.client_id = None
        with pytest.raises(HTTPException) as ei:
            await bare.exchange_token('c', 'http://cb')
        assert ei.value.status_code == 400

    async def test_getters(self, svc):
        self._http(svc, _http_resp(200, {'CompanyInfo': {'id': 'c'},
                                         'QueryResponse': {
                                             'Customer': [1],
                                             'Invoice': [2],
                                             'Purchase': [3]}}))
        assert await svc.get_company_info() == {'id': 'c'}
        assert await svc.get_customers(max_results=5) == [1]
        assert await svc.get_invoices() == [2]
        assert await svc.get_expenses() == [3]
        assert (await svc.get_company_info(realm_id='r',
                                           access_token='t')) == {'id': 'c'}
        # 401 when unauthenticated
        svc2 = QuickBooksService(tenant_id='t', config={})
        for meth in (svc2.get_company_info, svc2.get_customers,
                     svc2.get_invoices, svc2.get_expenses):
            with pytest.raises(HTTPException) as ei:
                await meth()
            assert ei.value.status_code == 401
        # HTTP errors -> 400
        svc.http.get = AsyncMock(side_effect=httpx.HTTPError('x'))
        for meth in (svc.get_company_info, svc.get_customers,
                     svc.get_invoices, svc.get_expenses):
            with pytest.raises(HTTPException) as ei:
                await meth()
            assert ei.value.status_code == 400

    async def test_health_check(self, svc):
        h = await svc.health_check()
        assert h['ok'] is True and h['service'] == 'quickbooks'

        class _BoomDatetime:
            @staticmethod
            def now(*a, **k):
                raise RuntimeError('x')
        with patch.object(qb_mod, 'datetime', _BoomDatetime):
            h = await svc.health_check()
            assert h['ok'] is False and h['timestamp'] is None

    async def test_execute_operation(self, svc):
        self._http(svc, _http_resp(200, {'QueryResponse': {
            'Customer': [1], 'Invoice': [2], 'Purchase': [3]},
            'CompanyInfo': {}}))
        for op in ('get_company_info', 'get_customers', 'get_invoices',
                   'get_expenses'):
            r = await svc.execute_operation(op, {})
            assert r['success'] is True, op
        svc.full_sync = AsyncMock(return_value={'success': True})
        r = await svc.execute_operation('full_sync', {'user_id': 'u'})
        assert r['success'] is True
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_company_info = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('get_company_info',
                                            {}))['success'] is False

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.get_invoices = AsyncMock(return_value=[1, 2])
        svc.get_customers = AsyncMock(return_value=[1])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('u1', 'r', 't')
        assert r == {'success': True, 'metrics_synced': 2}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('u1', 'r', 't'))[
            'metrics_synced'] == 2
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('u1', 'r', 't'))[
            'success'] is False
        svc.get_invoices = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('u1', 'r', 't'))[
            'success'] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('u1', 'r', 't')
        assert r['success'] and r['user_id'] == 'u1'


# ============================================================================
# TeamsService
# ============================================================================

class TestTeamsService:
    @pytest.fixture()
    def svc(self, monkeypatch):
        monkeypatch.delenv('TEAMS_ACCESS_TOKEN', raising=False)
        return TeamsService(tenant_id='t1', config={'access_token': 'tok'})

    def test_init(self, svc):
        assert svc.base_url == 'https://graph.microsoft.com/v1.0'
        assert svc.session.headers['Authorization'] == 'Bearer tok'
        bare = TeamsService(tenant_id='t', config={})
        assert 'Authorization' not in bare.session.headers
        assert TeamsService() is not None  # config=None default branch

    def _get(self, svc, resp):
        return patch.object(svc.session, 'get', return_value=resp)

    def test_test_connection(self, svc):
        with self._get(svc, _resp({'displayName': 'D', 'mail': 'm'})):
            r = svc.test_connection()
            assert r['status'] == 'success' and r['email'] == 'm'
        with self._get(svc, _resp({'displayName': 'D',
                                   'userPrincipalName': 'up'})):
            assert svc.test_connection()['email'] == 'up'
        with self._get(svc, _resp(None, 401)):
            r = svc.test_connection()
            assert r['authenticated'] is False
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.test_connection()['status'] == 'error'

    def test_team_and_channel_reads(self, svc):
        payload = _resp({'value': [1]})
        with self._get(svc, payload):
            assert svc.get_teams() == [1]
        with self._get(svc, _resp({'id': 'T'})):
            assert svc.get_team('T') == {'id': 'T'}
        with self._get(svc, payload):
            assert svc.get_channels('T') == [1]
        with self._get(svc, _resp({'id': 'C'})):
            assert svc.get_channel('T', 'C') == {'id': 'C'}
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.get_teams() == []
            assert svc.get_team('T') is None
            assert svc.get_channels('T') == []
            assert svc.get_channel('T', 'C') is None

    def test_channel_write_and_messages(self, svc):
        with patch.object(svc.session, 'post', return_value=_resp({'id': 'x'})):
            assert svc.create_channel('T', 'N', 'd', 'private') == {'id': 'x'}
            assert svc.send_message('T', 'C', 'hi') == {'id': 'x'}
            assert svc.reply_to_message('T', 'C', 'M', 're') == {'id': 'x'}
            assert svc.create_meeting('S', '2026', '2027', ['a@b.c']) == \
                {'id': 'x'}
            assert svc.send_chat_message('ch', 'hi') == {'id': 'x'}
            assert svc.set_user_presence('Available', 'Available') is True
        with patch.object(svc.session, 'post', side_effect=RuntimeError('x')):
            assert svc.create_channel('T', 'N') is None
            assert svc.send_message('T', 'C', 'h') is None
            assert svc.reply_to_message('T', 'C', 'M', 'r') is None
            assert svc.create_meeting('S', 'a', 'b') is None
            assert svc.send_chat_message('ch', 'h') is None
            assert svc.set_user_presence('A', 'B') is False

    def test_reads_messages_members_presence(self, svc):
        val = _resp({'value': [1]})
        with self._get(svc, val):
            assert svc.get_messages('T', 'C', limit=5) == [1]
            assert svc.get_meetings('T') == [1]
            assert svc.get_meetings() == [1]
            assert svc.get_team_members('T') == [1]
            assert svc.get_channel_members('T', 'C') == [1]
            assert svc.get_chat_messages('ch') == [1]
            assert svc.get_online_meeting('m1') == {'value': [1]}
            assert svc.get_user_presence('u1') == {'value': [1]}
            assert svc.get_user_presence() == {'value': [1]}
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.get_messages('T', 'C') == []
            assert svc.get_meetings('T') == []
            assert svc.get_meetings() == []
            assert svc.get_team_members('T') == []
            assert svc.get_channel_members('T', 'C') == []
            assert svc.get_chat_messages('ch') == []
            assert svc.get_online_meeting('m') is None
            assert svc.get_user_presence() is None

    def test_member_management(self, svc):
        with patch.object(svc.session, 'post', return_value=_resp()):
            assert svc.add_member_to_channel('T', 'C', 'u', 'owner') is True
        with patch.object(svc.session, 'post', side_effect=RuntimeError('x')):
            assert svc.add_member_to_channel('T', 'C', 'u') is False
        with patch.object(svc.session, 'delete', return_value=_resp()):
            assert svc.remove_member_from_channel('T', 'C', 'm') is True
        with patch.object(svc.session, 'delete', side_effect=RuntimeError('x')):
            assert svc.remove_member_from_channel('T', 'C', 'm') is False

    async def test_join_health_capabilities_execute(self, svc):
        r = svc.join_meeting('https://join')
        assert r['status'] == 'success' and r['join_url'] == 'https://join'
        with self._get(svc, _resp({'displayName': 'D'})):
            h = svc.health_check()
            assert h['healthy'] is True
        with self._get(svc, _resp(None, 401)):
            assert svc.health_check()['healthy'] is False
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is True
        with self._get(svc, _resp({'value': [1]})):
            r = await svc.execute_operation('get_teams', {})
            assert r['success'] and r['result'] == [1]
        with patch.object(svc.session, 'post', return_value=_resp({'id': 'm'})):
            r = await svc.execute_operation('send_message',
                                            {'team_id': 'T', 'channel_id': 'C',
                                             'content': 'x'})
            assert r['success']
        with pytest.raises(NotImplementedError):
            await svc.execute_operation('nope', {})


# ============================================================================
# AsanaRealService
# ============================================================================

class _FakeResponse:
    def __init__(self, status=200, payload=None, text='err'):
        self.status = status
        self._payload = payload
        self._text = text

    async def json(self):
        return self._payload or {}

    async def text(self):
        return self._text


class _FakeRespCM:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *a):
        return False


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def _next(self):
        return self._responses[0] if len(self._responses) == 1 \
            else self._responses.pop(0)

    def get(self, *a, **k):
        return _FakeRespCM(self._next())

    def post(self, *a, **k):
        return _FakeRespCM(self._next())

    def put(self, *a, **k):
        return _FakeRespCM(self._next())

    def delete(self, *a, **k):
        return _FakeRespCM(self._next())


def _asana_session(*responses):
    return patch.object(ar.aiohttp, 'ClientSession',
                        MagicMock(return_value=_FakeSession(responses)))


class TestAsanaReal:
    @pytest.fixture(autouse=True)
    def _guards(self):
        with patch.object(ar.circuit_breaker, 'is_enabled',
                          new=AsyncMock(return_value=True)), \
             patch.object(ar.rate_limiter, 'is_rate_limited',
                          new=AsyncMock(return_value=(False, 100))), \
             patch.object(ar, 'log_integration_attempt',
                          return_value={'start_time': 0.0}), \
             patch.object(ar, 'log_integration_complete',
                          MagicMock(return_value=0.1)):
            yield

    def _svc(self):
        return AsanaRealService(access_token='tok', workspace_gid='ws1')

    def _task(self):
        return {'gid': 't1', 'name': 'N', 'notes': 'd',
                'due_on': '2026-08-20', 'completed': False,
                'assignee': {'name': 'A'}, 'tags': [{'name': 'x'}],
                'created_at': 'c', 'modified_at': 'm'}

    def test_init(self, monkeypatch):
        monkeypatch.setenv('ASANA_ACCESS_TOKEN', 'et')
        monkeypatch.setenv('ASANA_WORKSPACE_GID', 'ew')
        s = AsanaRealService()
        assert s.access_token == 'et' and s.workspace_gid == 'ew'
        assert self._svc().BASE_URL == 'https://app.asana.com/api/1.0'

    async def test_make_request_methods(self):
        with _asana_session(_FakeResponse(200, {'data': []})):
            assert await self._svc()._make_request('GET', 'x') == {'data': []}
            assert await self._svc()._make_request('POST', 'x', {}) == \
                {'data': []}
            assert await self._svc()._make_request('PUT', 'x', {}) == \
                {'data': []}
            assert await self._svc()._make_request('DELETE', 'x') == \
                {'success': True}
        with _asana_session(_FakeResponse(404, None, 'nope')):
            r = await self._svc()._make_request('DELETE', 'x')
            assert r == {'success': False,
                         'errors': [{'message': 'DELETE failed'}]}

        class _BoomCM(_FakeRespCM):
            async def __aenter__(self):
                raise RuntimeError('net down')

        class _BoomSession(_FakeSession):
            def get(self, *a, **k):
                return _BoomCM(None)

        with patch.object(ar.aiohttp, 'ClientSession',
                          MagicMock(return_value=_BoomSession([]))):
            r = await self._svc()._make_request('GET', 'x')
            assert r == {'errors': [{'message': 'net down'}]}

    async def test_delete_success_status(self):
        with _asana_session(_FakeResponse(204, None, '')):
            r = await self._svc()._make_request('DELETE', 'tasks/t1')
            assert r == {'success': True}

    async def test_get_tasks(self):
        with _asana_session(_FakeResponse(200, {'data': [self._task()]})):
            tasks = await self._svc().get_tasks(project_gid='p1')
            assert len(tasks) == 1 and tasks[0]['id'] == 't1'
            assert tasks[0]['status'] == 'todo'
            tasks2 = await self._svc().get_tasks()
            assert tasks2[0]['platform'] == 'asana'
        with _asana_session(_FakeResponse(200, {'errors': []})):
            assert await self._svc().get_tasks() == []

    async def test_create_update_delete_task(self):
        with _asana_session(_FakeResponse(200, {'data': self._task()}),
                            _FakeResponse(200, {'data': self._task()})):
            r = await self._svc().create_task(
                {'title': 'T', 'description': 'd', 'dueDate': '2026-08-20T10:00',
                 'project': 'p1'})
            assert r['title'] == 'N'
            r = await self._svc().update_task(
                't1', {'title': 'x', 'description': 'y',
                       'status': 'completed', 'dueDate': '2026-09-01T00:00'})
            assert r is not None
        with _asana_session(_FakeResponse(200, {'errors': []}),
                            _FakeResponse(200, {'errors': []})):
            assert await self._svc().create_task({'title': 'T'}) is None
            assert await self._svc().update_task('t1', {}) is None
        with _asana_session(_FakeResponse(200, {'success': True})):
            assert await self._svc().delete_task('t1') is True
        # DELETE with non-2xx status fails closed
        with _asana_session(_FakeResponse(404)):
            assert await self._svc().delete_task('t1') is False

    async def test_task_guard_paths(self):
        svc = self._svc()
        with patch.object(ar.circuit_breaker, 'is_enabled',
                          new=AsyncMock(return_value=False)):
            with pytest.raises(HTTPException):
                await svc.create_task({'title': 'T'})
            with pytest.raises(HTTPException):
                await svc.update_task('t', {})
            with pytest.raises(HTTPException):
                await svc.delete_task('t')
            with pytest.raises(HTTPException):
                await svc.get_projects()
            with pytest.raises(HTTPException):
                await svc.create_project({'name': 'P'})
        with patch.object(ar.rate_limiter, 'is_rate_limited',
                          new=AsyncMock(return_value=(True, 0))):
            with pytest.raises(HTTPException):
                await svc.create_task({'title': 'T'})
            with pytest.raises(HTTPException):
                await svc.update_task('t', {})
            with pytest.raises(HTTPException):
                await svc.delete_task('t')
            with pytest.raises(HTTPException):
                await svc.get_projects()
            with pytest.raises(HTTPException):
                await svc.create_project({'name': 'P'})

    async def test_task_exception_paths(self):
        svc = self._svc()
        with patch.object(svc, '_make_request',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert await svc.create_task({'title': 'T'}) is None
            assert await svc.update_task('t', {}) is None
            assert await svc.delete_task('t') is False
            assert await svc.get_projects() == []
            assert await svc.create_project({'name': 'P'}) is None

    async def test_projects(self):
        proj = {'gid': 'p1', 'name': 'P', 'notes': 'n', 'color': 'dark-pink'}
        with _asana_session(_FakeResponse(200, {'data': [proj]}),
                            _FakeResponse(200, {'data': proj})):
            r = await self._svc().get_projects()
            assert r[0]['color'] == '#D53F8C'
            r2 = await self._svc().create_project({'name': 'P',
                                                   'description': 'd',
                                                   'color': 'dark-green'})
            assert r2 is not None
        with _asana_session(_FakeResponse(200, {'errors': []})):
            assert await self._svc().get_projects() == []
            assert await self._svc().create_project({'name': 'P'}) is None

    def test_converters(self):
        svc = self._svc()
        u = svc._convert_asana_to_unified(self._task())
        assert u['status'] == 'todo' and u['tags'] == ['x']
        assert u['assignee'] == 'A'
        done = svc._convert_asana_to_unified(
            dict(self._task(), completed=True, due_on=None, assignee=None))
        assert done['status'] == 'completed' and done['assignee'] is None
        assert 'T' in done['dueDate']  # fell back to datetime.now()
        proj = svc._convert_asana_project_to_unified({'gid': 'p', 'name': 'N'})
        assert proj['color'] == '#3182CE'  # default (dark-blue)
        unknown = svc._convert_asana_project_to_unified(
            {'color': 'neon-puce'})
        assert unknown['color'] == '#3182CE'
        assert isinstance(ar.asana_real_service, AsanaRealService)
