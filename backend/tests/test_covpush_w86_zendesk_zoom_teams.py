# -*- coding: utf-8 -*-
"""Coverage wave 86 — integrations.atom_zendesk_integration_service,
integrations.atom_zoom_integration, integrations.teams_enhanced_service.

No network, no LLM: all HTTP boundaries (httpx/aiohttp/Graph clients) are
mocked; circuit breaker / rate limiter / audit logging are patched at the
module level; Zoom ingestion pipeline and enterprise services are mocks.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_zendesk_integration_service as zd_mod
import integrations.atom_zoom_integration as zoom_mod
import integrations.teams_enhanced_service as te_mod
from integrations.atom_zendesk_integration_service import (
    AtomZendeskIntegrationService,
    SupportAnalyticsType,
    ZendeskAgent,
    ZendeskTicket,
    ZendeskTicketPriority,
    ZendeskTicketStatus,
    ZendeskTicketType,
    ZendeskUser,
)
from integrations.atom_zoom_integration import (
    AtomZoomIntegration,
    ZoomEvent,
    ZoomEventType,
    ZoomMeeting,
    ZoomMeetingType,
    ZoomUser,
    ZoomUserType,
)
from integrations.teams_enhanced_service import (
    TeamsChannel,
    TeamsEnhancedService,
    TeamsMessage,
    TeamsRateLimiter,
    TeamsWorkspace,
)


DT = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


# ============================================================================
# Helpers
# ============================================================================

def _resp(status_code=200, payload=None, text=''):
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = payload if payload is not None else {}
    return resp


def _httpx(monkeypatch, get=None, post=None, put=None):
    """Patch httpx.AsyncClient used inside zendesk/teams modules."""
    client = MagicMock()
    client.get = AsyncMock(return_value=get)
    client.post = AsyncMock(return_value=post)
    client.put = AsyncMock(return_value=put)
    cls = MagicMock()
    cls.return_value.__aenter__.return_value = client
    monkeypatch.setattr(zd_mod.httpx, 'AsyncClient', cls)
    return client


def _mk_zendesk(**overrides):
    cfg = {
        'zendesk_subdomain': 'test',
        'zendesk_api_token': 'tok',
        'zendesk_username': 'user@example.com',
        'enable_salesforce_integration': False,
        'ticket_auto_assignment': False,
        'priority_auto_classification': False,
        'sentiment_analysis': False,
        'ai_response_suggestions': False,
        'sla_monitoring': True,
        'escalation_rules': True,
        'cache': None,
        'database': None,
    }
    cfg.update(overrides)
    return AtomZendeskIntegrationService(config=cfg)


@pytest.fixture()
def zd(monkeypatch):
    svc = _mk_zendesk()
    # Patch core guards at module level
    cb = MagicMock()
    cb.is_enabled = AsyncMock(return_value=True)
    rl = MagicMock()
    rl.is_rate_limited = AsyncMock(return_value=(False, 10))
    monkeypatch.setattr(zd_mod, 'circuit_breaker', cb)
    monkeypatch.setattr(zd_mod, 'rate_limiter', rl)
    monkeypatch.setattr(zd_mod, 'log_integration_attempt', MagicMock(return_value={}))
    monkeypatch.setattr(zd_mod, 'log_integration_complete', MagicMock())
    monkeypatch.setattr(zd_mod, 'log_integration_call', MagicMock())
    monkeypatch.setattr(zd_mod, 'log_integration_error', MagicMock())
    svc._cb = cb
    svc._rl = rl
    return svc


def _mk_zoom(**overrides):
    cfg = {
        'api_key': 'k', 'api_secret': 's',
        'webhook_url': 'https://hook', 'webhook_secret': 'whsec',
        'enable_enterprise_features': True,
    }
    cfg.update(overrides)
    integ = AtomZoomIntegration(cfg)
    session = MagicMock()
    session.get = AsyncMock(return_value=_resp(200, {}))
    session.post = AsyncMock(return_value=_resp(201, {}))
    session.aclose = AsyncMock()
    integ.http_session = session
    return integ


def zoom_meeting(meeting_id='M1', host='h1', status='started', topic='Deploy sync'):
    return ZoomMeeting(
        meeting_id=meeting_id, topic=topic, meeting_type=ZoomMeetingType.SCHEDULED,
        host_id=host, start_time=DT, duration=30, timezone='UTC',
        agenda='quarterly agenda text', participants=[host], is_recorded=False,
        password=None, waiting_room=True, security_level='standard',
        created_at=DT, status=status, metadata={})


def zoom_event(event_id='E1', meeting_id='M1', user_id='u1', etype=ZoomEventType.MEETING_PARTICIPANT_JOINED):
    return ZoomEvent(
        event_id=event_id, event_type=etype, meeting_id=meeting_id, user_id=user_id,
        timestamp=DT, data={'k': 'v'}, security_flags={}, compliance_flags={},
        metadata={})


FERNET_KEY = __import__('base64').urlsafe_b64encode(b'0123456789abcdef0123456789abcdef').decode()


@pytest.fixture()
def teams(monkeypatch):
    monkeypatch.setattr(te_mod, 'msal', None)
    redis = MagicMock()
    svc = TeamsEnhancedService(tenant_id='t1', config={
        'client_id': 'cid', 'client_secret': 'sec', 'redirect_uri': 'https://cb',
        'encryption_key': FERNET_KEY, 'redis': {'client': redis}, 'database': None})
    redis.get.return_value = None
    svc.redis = redis
    return svc


def mk_team_workspace(team_id='T1', token=None):
    return TeamsWorkspace(
        team_id=team_id, name='Team', description='d', display_name='Team One',
        visibility='private', mail_nickname='team', created_at=DT, created_by='u1',
        tenant_id='t1', access_token=token, refresh_token=None)


def graph_client(teams_get=None, channels_get=None, messages_post=None,
                 messages_get=None):
    client = MagicMock()
    client._default_headers = {'Authorization': 'Bearer tok'}
    client.teams.get = AsyncMock(return_value=teams_get)
    client.teams.__getitem__.return_value.channels.get = AsyncMock(
        return_value=channels_get)
    chan = client.teams.__getitem__.return_value.channels.__getitem__.return_value
    chan.messages.post = AsyncMock(return_value=messages_post)
    chan.messages.get = AsyncMock(return_value=messages_get)
    chan.messages.__getitem__.return_value.replies.post = AsyncMock(
        return_value=messages_post)
    chan.get = AsyncMock(return_value=SimpleNamespace(
        additional_data={'siteId': 'site1'}))
    return client


# ============================================================================
# Zendesk — initialization & lifecycle
# ============================================================================

async def test_zd_initialize_success(zd, monkeypatch):
    _httpx(monkeypatch, get=_resp(200, {'ticket_count': {'value': 3}}))
    assert await zd.initialize() is True
    assert zd.is_initialized is True


async def test_zd_initialize_connection_failure(zd, monkeypatch):
    _httpx(monkeypatch, get=_resp(500))
    assert await zd.initialize() is False


async def test_zd_initialize_with_salesforce(zd, monkeypatch):
    _httpx(monkeypatch, get=_resp(200, {}))
    zd.zendesk_config['enable_salesforce_integration'] = True
    # salesforce import fails (phantom module) -> integration stays None
    await zd._initialize_salesforce_integration()
    assert zd.salesforce_integration is None
    # with a stub salesforce module present
    fake_sf_mod = SimpleNamespace(atom_salesforce_integration=object())
    with patch.dict('sys.modules', {'atom_salesforce_integration': fake_sf_mod}):
        await zd._initialize_salesforce_integration()
        assert zd.salesforce_integration is fake_sf_mod.atom_salesforce_integration
    zd.salesforce_integration = MagicMock()
    assert await zd._initialize_salesforce_connection() is True


async def test_zd_test_connection_branches(zd, monkeypatch):
    client = _httpx(monkeypatch, get=_resp(200, {}))
    assert await zd._test_zendesk_connection() is True
    client.get = AsyncMock(return_value=_resp(404))
    with pytest.raises(Exception):
        await zd._test_zendesk_connection()
    client.get = AsyncMock(side_effect=RuntimeError('net'))
    with pytest.raises(Exception):
        await zd._test_zendesk_connection()


def test_zd_auth_headers():
    svc = _mk_zendesk(zendesk_oauth_token='oatok')
    headers = svc._get_auth_headers()
    assert headers['Authorization'] == 'Bearer oatok'
    svc2 = _mk_zendesk()
    assert 'Basic ' in svc2._get_auth_headers()['Authorization']
    svc3 = _mk_zendesk(zendesk_api_token=None)
    with pytest.raises(Exception):
        svc3._get_auth_headers()


async def test_zd_setup_stubs_and_close(zd):
    assert await zd._setup_webhooks() is None
    assert await zd._setup_ticket_workflows() is None
    assert await zd._setup_escalation_rules() is None
    assert await zd._setup_enterprise_features() is True
    assert await zd._setup_security_and_compliance() is True
    assert await zd._load_existing_data() is True
    assert await zd._start_monitoring() is True
    await zd.close()


# ============================================================================
# Zendesk — ticket CRUD
# ============================================================================

_TICKET = {'id': 42, 'subject': 'Broken build', 'status': 'open',
           'priority': 'urgent', 'tags': ['ci'], 'assignee_id': 'a1'}


async def test_zd_create_ticket_success(zd, monkeypatch):
    client = _httpx(monkeypatch, post=_resp(201, {'ticket': _TICKET}))
    zd._cache_ticket = AsyncMock()
    zd._trigger_ticket_workflows = AsyncMock()
    zd.platform_integrations['slack'] = MagicMock()
    zd.platform_integrations['slack'].send_notification = AsyncMock()
    res = await zd.create_ticket(
        {'subject': 'Broken build', 'description': 'ci down',
         'requester_name': 'Bob', 'requester_email': 'b@x.com',
         'priority': 'urgent', 'type': 'incident', 'tags': ['ci']},
        platform='slack')
    assert res['success'] is True and res['ticket_id'] == 42
    zd._trigger_ticket_workflows.assert_awaited_once()
    zd.platform_integrations['slack'].send_notification.assert_awaited_once()


async def test_zd_create_ticket_api_error(zd, monkeypatch):
    client = _httpx(monkeypatch, post=_resp(400, text='bad payload'))
    res = await zd.create_ticket({'subject': 'x'})
    assert res['success'] is False


async def test_zd_create_ticket_guards(zd, monkeypatch):
    _httpx(monkeypatch)
    zd._cb.is_enabled = AsyncMock(return_value=False)
    assert (await zd.create_ticket({}))['success'] is False
    zd._cb.is_enabled = AsyncMock(return_value=True)
    zd._rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    assert (await zd.create_ticket({}))['success'] is False
    zd._rl.is_rate_limited = AsyncMock(return_value=(False, 10))
    zd._cb.is_enabled = AsyncMock(side_effect=RuntimeError('x'))
    assert (await zd.create_ticket({}))['success'] is False


async def test_zd_create_ticket_security_block(zd, monkeypatch):
    _httpx(monkeypatch)
    zd.zendesk_config['enable_enterprise_features'] = True
    zd.enterprise_security = MagicMock()
    zd.enterprise_security.check = AsyncMock(
        return_value={'allowed': False, 'reason': 'pii detected'})
    res = await zd.create_ticket({'subject': 'x'})
    assert res['success'] is False and res['error'] == 'pii detected'


async def test_zd_create_ticket_with_ai_and_assignment(zd, monkeypatch):
    _httpx(monkeypatch, post=_resp(201, {'ticket': _TICKET}))
    zd._cache_ticket = AsyncMock()
    zd._trigger_ticket_workflows = AsyncMock()
    zd.zendesk_config['priority_auto_classification'] = True
    zd.zendesk_config['sentiment_analysis'] = True
    zd.zendesk_config['ticket_auto_assignment'] = True
    zd._analyze_ticket_with_ai = AsyncMock(
        return_value={'suggested_priority': 'urgent'})
    zd._auto_assign_ticket = AsyncMock(return_value='agent9')
    res = await zd.create_ticket({'subject': 'x'})
    assert res['success'] is True
    zd._auto_assign_ticket.assert_awaited_once()
    zd._analyze_ticket_with_ai.assert_awaited_once()


async def test_zd_update_ticket(zd, monkeypatch):
    zd._get_ticket = AsyncMock(return_value=_TICKET)
    zd._cache_ticket = AsyncMock()
    zd._check_sla_compliance = AsyncMock()
    zd._check_escalation = AsyncMock()
    zd._trigger_ticket_workflows = AsyncMock()
    client = _httpx(monkeypatch, put=_resp(200, {'ticket': _TICKET}))
    res = await zd.update_ticket(42, {'status': 'solved', 'priority': 'urgent',
                                      'public_comment': False},
                                 platform=None, comment='fixed it')
    assert res['success'] is True
    # not found
    zd._get_ticket = AsyncMock(return_value=None)
    assert (await zd.update_ticket(42, {}))['error'] == 'Ticket not found'
    # API failure
    zd._get_ticket = AsyncMock(return_value=_TICKET)
    client.put = AsyncMock(return_value=_resp(500))
    assert (await zd.update_ticket(42, {}))['success'] is False
    # guards
    zd._cb.is_enabled = AsyncMock(return_value=False)
    assert (await zd.update_ticket(42, {}))['success'] is False
    zd._cb.is_enabled = AsyncMock(return_value=True)
    zd._rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    assert (await zd.update_ticket(42, {}))['success'] is False
    zd._rl.is_rate_limited = AsyncMock(return_value=(False, 1))
    zd._get_ticket = AsyncMock(side_effect=RuntimeError('db'))
    assert (await zd.update_ticket(42, {}))['success'] is False


async def test_zd_get_tickets(zd, monkeypatch):
    page1 = _resp(200, {'tickets': [{'id': 1, 'status': 'open'}],
                        'next_page': 'https://next'})
    client = _httpx(monkeypatch, get=page1)
    second = _resp(200, {'tickets': [{'id': 2, 'status': 'solved'}],
                         'next_page': None})
    client.get = AsyncMock(side_effect=[page1, second])
    tickets = await zd.get_tickets({'status': 'open', 'priority': 'urgent',
                                    'assignee_id': 'a1', 'created_since': 'x',
                                    'limit': 500})
    assert len(tickets) == 2
    assert zd.analytics_metrics['open_tickets'] == 1
    assert zd.analytics_metrics['closed_tickets'] == 1
    # API failure and exception
    client.get = AsyncMock(return_value=_resp(500))
    assert await zd.get_tickets() == []
    client.get = AsyncMock(side_effect=RuntimeError('net'))
    assert await zd.get_tickets() == []


async def test_zd_get_ticket_info(zd, monkeypatch):
    zd._get_ticket = AsyncMock(return_value=_TICKET)
    assert (await zd.get_ticket_info(42)) == _TICKET
    zd._cb.is_enabled = AsyncMock(return_value=False)
    with pytest.raises(Exception):
        await zd.get_ticket_info(42)
    zd._cb.is_enabled = AsyncMock(return_value=True)
    zd._rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    with pytest.raises(Exception):
        await zd.get_ticket_info(42)


async def test_zd_create_ticket_comment(zd, monkeypatch):
    client = _httpx(monkeypatch, put=_resp(200, {'ticket': _TICKET}))
    res = await zd.create_ticket_comment(42, 'looking into it', public=False)
    assert res['success'] is True
    client.put = AsyncMock(return_value=_resp(400, text='nope'))
    assert (await zd.create_ticket_comment(42, 'x'))['success'] is False
    client.put = AsyncMock(side_effect=RuntimeError('net'))
    assert (await zd.create_ticket_comment(42, 'x'))['success'] is False
    zd._cb.is_enabled = AsyncMock(return_value=False)
    assert (await zd.create_ticket_comment(42, 'x'))['success'] is False


async def test_zd_private_get_ticket(zd, monkeypatch):
    cache = MagicMock()
    cache.get = AsyncMock(return_value=_TICKET)
    cache.set = AsyncMock()
    zd.cache = cache
    assert await zd._get_ticket(42) == _TICKET  # cache hit
    cache.get = AsyncMock(return_value=None)
    client = _httpx(monkeypatch, get=_resp(200, {'ticket': _TICKET}))
    assert await zd._get_ticket(42) == _TICKET
    client.get = AsyncMock(return_value=_resp(404))
    assert await zd._get_ticket(42) is None
    client.get = AsyncMock(side_effect=RuntimeError('x'))
    assert await zd._get_ticket(42) is None


# ============================================================================
# Zendesk — AI / agents / helpers
# ============================================================================

async def test_zd_analyze_ticket_with_ai(zd, monkeypatch):
    # AIRequest unavailable in this runtime -> defaults
    monkeypatch.setattr(zd_mod, 'AIRequest', None, raising=False)
    out = await zd._analyze_ticket_with_ai({'priority': 'low'})
    assert out['suggested_priority'] == 'low'
    # success path with mocked AI plumbing
    monkeypatch.setattr(zd_mod, 'AIRequest', MagicMock())
    monkeypatch.setattr(zd_mod, 'AITaskType', MagicMock(CONTENT_ANALYSIS='ca'),
                        raising=False)
    monkeypatch.setattr(zd_mod, 'AIModelType', MagicMock(GPT_4='g4'),
                        raising=False)
    monkeypatch.setattr(zd_mod, 'AIServiceType', MagicMock(OPENAI='oa'),
                        raising=False)
    zd.ai_service = MagicMock()
    resp = MagicMock(ok=True, output_data={
        'suggested_priority': 'urgent', 'sentiment': 'angry',
        'urgency_score': 0.9, 'suggested_agent_skills': ['k8s']})
    zd.ai_service.process_ai_request = AsyncMock(return_value=resp)
    out = await zd._analyze_ticket_with_ai({})
    assert out['suggested_priority'] == 'urgent'
    assert out['suggested_agent_skills'] == ['k8s']
    # not-ok response
    resp2 = MagicMock(ok=False, output_data=None)
    zd.ai_service.process_ai_request = AsyncMock(return_value=resp2)
    out = await zd._analyze_ticket_with_ai({})
    assert out['sentiment'] == 'neutral'
    # exception
    zd.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
    out = await zd._analyze_ticket_with_ai({})
    assert out['estimated_resolution_time'] == 60


async def test_zd_auto_assign(zd):
    zd._get_available_agents = AsyncMock(return_value=[])
    assert await zd._auto_assign_ticket({}) is None
    zd.agent_skills['a1'] = ['k8s']
    zd._get_agent_workload = AsyncMock(return_value=2)
    zd._get_available_agents = AsyncMock(
        return_value=[{'id': 'a1', 'role': 'agent'}])
    assert await zd._auto_assign_ticket({'suggested_agent_skills': ['k8s']}) == 'a1'
    # workload full -> falls through to min-workload agent
    zd._get_agent_workload = AsyncMock(return_value=9)
    assert await zd._auto_assign_ticket({'suggested_agent_skills': ['k8s']}) == 'a1'
    # no skills matched, still lowest workload agent
    assert await zd._auto_assign_ticket({}) == 'a1'
    zd._get_available_agents = AsyncMock(side_effect=RuntimeError('x'))
    assert await zd._auto_assign_ticket({}) is None


async def test_zd_get_available_agents(zd, monkeypatch):
    client = _httpx(monkeypatch, get=_resp(200, {'users': [
        {'id': 'a1', 'role': 'agent'}, {'id': 'u2', 'role': 'end-user'}]}))
    agents = await zd._get_available_agents()
    assert agents == [{'id': 'a1', 'role': 'agent'}]
    client.get = AsyncMock(return_value=_resp(500))
    assert await zd._get_available_agents() == []
    client.get = AsyncMock(side_effect=RuntimeError('x'))
    assert await zd._get_available_agents() == []


async def test_zd_agent_workload(zd):
    zd.get_tickets = AsyncMock(return_value=[{}, {}, {}])
    assert await zd._get_agent_workload('a1') == 3
    zd.get_tickets = AsyncMock(side_effect=RuntimeError('x'))
    assert await zd._get_agent_workload('a1') == 0


async def test_zd_security_check(zd):
    assert (await zd._perform_security_check({}))['passed'] is True
    zd.enterprise_security = None
    assert (await zd._perform_security_check({}))['passed'] is True
    zd.enterprise_security = MagicMock()
    zd.enterprise_security.check = AsyncMock(
        return_value={'allowed': False, 'reason': 'no'})
    chk = await zd._perform_security_check({})
    assert chk['passed'] is False and chk['reason'] == 'no'
    zd.enterprise_security.check = AsyncMock(return_value={'allowed': True})
    assert (await zd._perform_security_check({}))['passed'] is True
    zd.enterprise_security.check = AsyncMock(side_effect=RuntimeError('x'))
    assert (await zd._perform_security_check({}))['passed'] is True


async def test_zd_cache_ticket(zd):
    zd.cache = MagicMock()
    zd.cache.set = AsyncMock(side_effect=RuntimeError('x'))
    await zd._cache_ticket({'id': 1})  # exception swallowed


async def test_zd_workflows_and_sync(zd):
    zd.enterprise_automation = None
    await zd._trigger_ticket_workflows({}, 'created')
    zd.enterprise_automation = MagicMock()
    zd.enterprise_automation._handle_event_trigger = AsyncMock()
    await zd._trigger_ticket_workflows({}, 'updated')
    zd.enterprise_automation._handle_event_trigger.assert_awaited_once()
    zd.enterprise_automation._handle_event_trigger = AsyncMock(
        side_effect=RuntimeError('x'))
    await zd._trigger_ticket_workflows({}, 'updated')  # swallowed

    zd.salesforce_integration = None
    await zd._sync_ticket_to_salesforce({})
    sf = MagicMock()
    sf.sync_ticket = AsyncMock()
    zd.salesforce_integration = sf
    await zd._sync_ticket_to_salesforce({'id': 1})
    sf.sync_ticket.assert_awaited_once()
    sf.sync_ticket = AsyncMock(side_effect=RuntimeError('x'))
    await zd._sync_ticket_to_salesforce({})  # swallowed


async def test_zd_notify_platforms(zd):
    zd.platform_integrations = {}
    await zd._notify_platform_ticket_created({'id': 1}, 'slack')
    await zd._notify_platform_ticket_updated({'id': 1}, 'slack')
    integ = MagicMock()
    integ.send_notification = AsyncMock()
    zd.platform_integrations['slack'] = integ
    await zd._notify_platform_ticket_created({'id': 1, 'subject': 's'}, 'slack')
    await zd._notify_platform_ticket_updated({'id': 1, 'subject': 's'}, 'slack')
    assert integ.send_notification.await_count == 2
    integ.send_notification = AsyncMock(side_effect=RuntimeError('x'))
    await zd._notify_platform_ticket_created({}, 'slack')
    await zd._notify_platform_ticket_updated({}, 'slack')


async def test_zd_sla_and_escalation(zd):
    await zd._check_sla_compliance({'priority': 'urgent'})
    await zd._check_sla_compliance({'priority': 'bogus'})
    before = zd.analytics_metrics['escalation_rate']
    await zd._check_escalation({'priority': 'urgent'})
    assert zd.analytics_metrics['escalation_rate'] == before + 1.0
    await zd._check_escalation({'priority': 'low'})


# ============================================================================
# Zendesk — analytics
# ============================================================================

async def test_zd_analytics_generators(zd):
    tickets = [
        {'response_time': 100, 'resolution_time': 500,
         'satisfaction_rating': 4.5, 'priority': 'urgent', 'type': 'incident',
         'assignee_id': 'a1', 'escalated': True, 'resolved_first_contact': True},
        {'response_time': 400, 'resolution_time': 2000,
         'satisfaction_rating': 'bad', 'priority': 'low', 'type': 'question',
         'assignee_id': 'a1', 'escalated': False},
        {'response_time': None},
    ]
    resp = await zd._generate_response_time_analytics(tickets)
    assert resp['tickets_measured'] == 2
    res = await zd._generate_resolution_time_analytics(tickets)
    assert res['tickets_measured'] == 2
    sat = await zd._generate_satisfaction_analytics(tickets)
    assert sat['ratings_count'] == 1
    vol = await zd._generate_volume_analytics(tickets)
    assert vol['total_tickets'] == 3
    perf = await zd._generate_agent_performance_analytics(tickets)
    assert perf['agent_count'] == 2
    esc = await zd._generate_escalation_analytics(tickets)
    assert esc['escalated_count'] == 1
    fcr = await zd._generate_fcr_analytics(tickets)
    assert fcr['fcr_count'] == 1
    # empty inputs
    assert (await zd._generate_response_time_analytics([]))['tickets_measured'] == 0
    assert (await zd._generate_satisfaction_analytics([]))['average_satisfaction'] == 0.0
    assert (await zd._generate_escalation_analytics([]))['escalation_rate'] == 0.0
    assert (await zd._generate_fcr_analytics([]))['first_contact_resolution_rate'] == 0.0


async def test_zd_generate_support_analytics_all_types(zd):
    zd.get_tickets = AsyncMock(return_value=[
        {'response_time': 100, 'resolution_time': 300,
         'satisfaction_rating': 4.0, 'escalated': True,
         'resolved_first_contact': True}])
    for at in SupportAnalyticsType:
        res = await zd.generate_support_analytics(at, '7d')
        assert res['success'] is True
        assert 'analytics' in res


async def test_zd_generate_support_analytics_ai(zd, monkeypatch):
    monkeypatch.setattr(zd_mod, 'AIRequest', MagicMock(), raising=False)
    zd.get_tickets = AsyncMock(return_value=[])
    zd.zendesk_config['ai_response_suggestions'] = True
    zd._generate_ai_insights = AsyncMock(return_value={'insights': ['i']})
    res = await zd.generate_support_analytics(SupportAnalyticsType.TICKET_VOLUME)
    assert res['analytics']['metrics']['ai_insights'] == {'insights': ['i']}
    # guard branches
    zd._cb.is_enabled = AsyncMock(return_value=False)
    assert (await zd.generate_support_analytics(
        SupportAnalyticsType.TICKET_VOLUME))['success'] is False
    zd._cb.is_enabled = AsyncMock(return_value=True)
    zd._rl.is_rate_limited = AsyncMock(return_value=(True, 0))
    assert (await zd.generate_support_analytics(
        SupportAnalyticsType.TICKET_VOLUME))['success'] is False
    zd._rl.is_rate_limited = AsyncMock(return_value=(False, 5))
    zd.get_tickets = AsyncMock(side_effect=RuntimeError('x'))
    assert (await zd.generate_support_analytics(
        SupportAnalyticsType.TICKET_VOLUME))['success'] is False


async def test_zd_generate_ai_insights(zd, monkeypatch):
    zd.ai_service = None
    out = await zd._generate_ai_insights({}, [])
    assert out == {'insights': [], 'recommendations': []}
    monkeypatch.setattr(zd_mod, 'AIRequest', MagicMock(), raising=False)
    for name, val in (('AITaskType', MagicMock(CONTENT_ANALYSIS='ca')),
                      ('AIModelType', MagicMock(GPT_4='g4')),
                      ('AIServiceType', MagicMock(OPENAI='oa'))):
        monkeypatch.setattr(zd_mod, name, val, raising=False)
    zd.ai_service = MagicMock()
    resp = MagicMock(ok=True, output_data={'insights': ['x']})
    zd.ai_service.process_ai_request = AsyncMock(return_value=resp)
    assert (await zd._generate_ai_insights({}, []))['insights'] == ['x']
    resp2 = MagicMock(ok=False, output_data=None)
    zd.ai_service.process_ai_request = AsyncMock(return_value=resp2)
    assert await zd._generate_ai_insights({}, []) == {
        'insights': [], 'recommendations': []}


async def test_zd_service_status(zd):
    status = await zd.get_service_status()
    assert status['service'] == 'zendesk_integration'
    assert status['status'] == 'inactive'
    zd.is_initialized = True
    assert (await zd.get_service_status())['status'] == 'active'


def test_zd_dataclasses():
    ticket = ZendeskTicket(
        ticket_id='1', subject='s', description='d', requester_id='r',
        requester_email='e', requester_name='n', status=ZendeskTicketStatus.NEW,
        priority=ZendeskTicketPriority.URGENT, ticket_type=ZendeskTicketType.TASK,
        assignee_id=None, group_id=None, created_at=DT, updated_at=DT,
        due_at=None, tags=[], custom_fields={}, comments=[], attachments=[],
        satisfaction_rating=None, platform='zendesk', metadata={})
    assert ticket.ticket_id == '1'
    user = ZendeskUser(user_id='u', email='e', name='n', role='agent',
                       phone=None, organization_id=None, tags=[],
                       custom_fields={}, created_at=DT, updated_at=DT, metadata={})
    agent = ZendeskAgent(agent_id='a', email='e', name='n', role='agent',
                         group_ids=[], skills=[], availability='online',
                         status='active', metrics={}, created_at=DT,
                         updated_at=DT, metadata={})
    assert user.role == 'agent' and agent.agent_id == 'a'


# ============================================================================
# Zoom — initialization
# ============================================================================

async def test_zoom_initialize_no_credentials(monkeypatch):
    for var in ('ZOOM_API_KEY', 'ZOOM_API_SECRET', 'ZOOM_CLIENT_ID',
                'ZOOM_CLIENT_SECRET'):
        monkeypatch.delenv(var, raising=False)
    integ = _mk_zoom(api_key=None, api_secret=None, client_id=None,
                     client_secret=None)
    assert await integ.initialize() is False


async def test_zoom_initialize_success():
    integ = _mk_zoom(webhook_url=None, enable_enterprise_features=False)
    integ._setup_automation = AsyncMock()
    assert await integ.initialize() is True
    assert integ.is_initialized


async def test_zoom_initialize_with_everything():
    integ = _mk_zoom()
    integ.enterprise_security = MagicMock()
    integ.enterprise_automation = MagicMock()
    integ.enterprise_automation.create_integration_automation = AsyncMock(
        return_value={'ok': True})
    assert await integ.initialize() is True
    assert integ.security_policies and integ.compliance_rules
    assert integ.automation_triggers and integ.webhook_handlers
    assert integ.security_monitoring and integ.compliance_monitoring


async def test_zoom_initialize_failure():
    integ = _mk_zoom()
    integ._test_api_connection = AsyncMock(side_effect=RuntimeError('x'))
    assert await integ.initialize() is False


async def test_zoom_test_api_connection():
    integ = _mk_zoom()
    await integ._test_api_connection()  # no token -> warning
    integ.oauth_token = 'tok'
    await integ._test_api_connection()  # 200
    integ.http_session.get = AsyncMock(return_value=_resp(500))
    await integ._test_api_connection()  # failure logged
    integ.http_session.get = AsyncMock(side_effect=RuntimeError('net'))
    await integ._test_api_connection()  # exception swallowed


async def test_zoom_get_oauth_token():
    integ = _mk_zoom()
    await integ._get_oauth_token()  # no token -> warning path
    integ.oauth_token = 'tok'
    integ.oauth_token_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await integ._get_oauth_token()  # cached -> early return


async def test_zoom_setup_webhook():
    integ = _mk_zoom()
    await integ._setup_webhook()  # 201
    integ.http_session.post = AsyncMock(return_value=_resp(500))
    await integ._setup_webhook()
    integ.http_session.post = AsyncMock(side_effect=RuntimeError('x'))
    await integ._setup_webhook()


async def test_zoom_setup_enterprise_missing():
    integ = _mk_zoom()
    integ.enterprise_security = None
    integ.enterprise_automation = None
    await integ._setup_enterprise_features()  # warning branch


async def test_zoom_setup_automation():
    integ = _mk_zoom()
    integ.enterprise_automation = None
    await integ._setup_automation()  # warning
    ea = MagicMock()
    ea.create_integration_automation = AsyncMock(return_value={'ok': False,
                                                               'error': 'bad'})
    integ.enterprise_automation = ea
    await integ._setup_automation()
    ea.create_integration_automation = AsyncMock(return_value={'ok': True})
    await integ._setup_automation()
    ea.create_integration_automation = AsyncMock(side_effect=RuntimeError('x'))
    await integ._setup_automation()


async def test_zoom_load_existing_data_and_close():
    integ = _mk_zoom()
    await integ._load_existing_data()
    await integ.close()
    integ.http_session.aclose.assert_awaited_once()
    integ.http_session = None
    await integ.close()


# ============================================================================
# Zoom — intelligent API surface
# ============================================================================

async def test_zoom_intelligent_workspaces_channels():
    integ = _mk_zoom()
    integ.active_meetings = {'M1': zoom_meeting('M1', host='h1'),
                             'M2': zoom_meeting('M2', host='h2', status='ended')}
    ws = await integ.get_intelligent_workspaces('h1')
    assert len(ws) == 1 and ws[0]['id'] == 'M1'
    assert ws[0]['permissions']['can_manage'] is True
    chans = await integ.get_intelligent_channels('M1', 'h1')
    assert chans[0]['meeting_type'] == 'scheduled'
    assert await integ.get_intelligent_channels('NOPE', 'h1') == []


async def test_zoom_send_intelligent_message():
    integ = _mk_zoom()
    res = await integ.send_intelligent_message('NOPE', 'hi')
    assert res['success'] is False and res['error'] == 'Meeting not found'
    integ.active_meetings['M1'] = zoom_meeting()
    integ._send_chat_message = AsyncMock(
        return_value={'success': True, 'message_id': 'm1'})
    integ._log_message_event = AsyncMock()
    res = await integ.send_intelligent_message('M1', 'hi', metadata={'a': 1})
    assert res['success'] is True
    integ._log_message_event.assert_awaited_once()
    integ._send_chat_message = AsyncMock(return_value={'success': False})
    assert (await integ.send_intelligent_message('M1', 'x'))['success'] is False
    integ._send_chat_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await integ.send_intelligent_message('M1', 'x'))['success'] is False


async def test_zoom_send_chat_message():
    integ = _mk_zoom()
    integ.oauth_token = 'tok'
    integ.http_session.post = AsyncMock(
        return_value=_resp(201, {'message_id': 'm9'}))
    res = await integ._send_chat_message('M1', 'hello')
    assert res['success'] is True and res['message_id'] == 'm9'
    integ.http_session.post = AsyncMock(
        return_value=_resp(400, {'message': 'denied'}))
    assert (await integ._send_chat_message('M1', 'x'))['error'] == 'denied'
    integ.http_session.post = AsyncMock(side_effect=RuntimeError('net'))
    assert (await integ._send_chat_message('M1', 'x'))['success'] is False


async def test_zoom_intelligent_search():
    integ = _mk_zoom()
    integ.active_meetings = {'M1': zoom_meeting(),
                             'M2': ZoomMeeting(
                                 meeting_id='M2', topic='standup',
                                 meeting_type=ZoomMeetingType.INSTANT,
                                 host_id='h', start_time=DT, duration=15,
                                 timezone='UTC', agenda=None, participants=[],
                                 is_recorded=False, password=None,
                                 waiting_room=False, security_level='standard',
                                 created_at=DT, status='started', metadata={})}
    res = await integ.perform_intelligent_search('deploy', 'h1')
    assert res and res[0]['id'] == 'M1'
    assert res[0]['relevance_score'] > 0
    res = await integ.perform_intelligent_search('standup', 'h1',
                                                 workspace_id='M2')
    assert res[0]['id'] == 'M2' and res[0]['snippet'] == 'No agenda'
    # long agenda snippet truncation
    long = zoom_meeting()
    long.agenda = 'x' * 200
    integ.active_meetings['M3'] = long
    res = await integ.perform_intelligent_search('deploy', 'h1')
    assert any('...' in r['snippet'] for r in res)
    assert integ._calculate_relevance_score('a b', 'a c') == 0.5
    assert integ._calculate_relevance_score('', 'x') == 0.0
    integ.ai_service = MagicMock()
    integ._perform_ai_search = AsyncMock(return_value=[{'id': 'ai1'}])
    res = await integ.perform_intelligent_search('deploy', 'h1')
    assert any(r['id'] == 'ai1' for r in res)


async def test_zoom_ai_search(monkeypatch):
    integ = _mk_zoom()
    assert await integ._perform_ai_search('q') == []  # no service
    monkeypatch.setattr(zoom_mod, 'AIRequest', None, raising=False)
    integ.ai_service = MagicMock()
    assert await integ._perform_ai_search('q') == []  # AIRequest unavailable
    monkeypatch.setattr(zoom_mod, 'AIRequest', MagicMock(), raising=False)
    monkeypatch.setattr(zoom_mod, 'AITaskType', MagicMock(SEARCH_QUERY='sq'),
                        raising=False)
    monkeypatch.setattr(zoom_mod, 'AIModelType', MagicMock(GPT_4='g4'),
                        raising=False)
    monkeypatch.setattr(zoom_mod, 'AIServiceType', MagicMock(OPENAI='oa'),
                        raising=False)
    resp = MagicMock(ok=True, output_data={'results': [{'id': 'r'}]})
    integ.ai_service.process_ai_request = AsyncMock(return_value=resp)
    assert await integ._perform_ai_search('q') == [{'id': 'r'}]
    resp2 = MagicMock(ok=False, output_data=None)
    integ.ai_service.process_ai_request = AsyncMock(return_value=resp2)
    assert await integ._perform_ai_search('q') == []
    integ.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await integ._perform_ai_search('q') == []


async def test_zoom_conversation_history_and_status():
    integ = _mk_zoom()
    integ.meeting_history = {
        'M1': [zoom_event('E1', user_id='u1'),
               zoom_event('E2', user_id='u2'),
               zoom_event('E3', user_id='u1')]}
    hist = await integ.get_user_conversation_history('u1', 'M1', limit=1)
    assert len(hist) == 1 and hist[0]['platform'] == 'zoom'
    status = await integ.get_service_status()
    assert status['platform'] == 'zoom' and status['status'] == 'inactive'
    integ.is_initialized = True
    assert (await integ.get_service_status())['status'] == 'active'


# ============================================================================
# Zoom — webhook event handlers
# ============================================================================

def _evt(meeting_id='M1', participant=None, recordings=None, topic=None):
    obj = {'id': meeting_id}
    if topic:
        obj['topic'] = topic
        obj['host_id'] = 'h1'
    if participant:
        obj['participant'] = participant
    if recordings is not None:
        obj['recording_files'] = recordings
    return {'payload': {'object': obj}}


async def test_zoom_handle_meeting_started(monkeypatch):
    integ = _mk_zoom()
    pipeline = MagicMock()
    monkeypatch.setattr(zoom_mod, 'atom_ingestion_pipeline', pipeline)
    monkeypatch.setattr(zoom_mod, 'RecordType',
                        SimpleNamespace(MEETING=SimpleNamespace(value='meeting')))
    integ._trigger_automations = AsyncMock()
    await integ._handle_meeting_started(_evt(topic='Kickoff'))
    assert 'M1' in integ.active_meetings
    assert integ.analytics_metrics['total_meetings'] == 1
    pipeline.ingest_record.assert_called_once()
    # ingestion failure swallowed
    pipeline.ingest_record.side_effect = RuntimeError('lance')
    await integ._handle_meeting_started(_evt(meeting_id='M2', topic='Two'))
    # exception path (bad event shape)
    await integ._handle_meeting_started({'bad': 1})


async def test_zoom_handle_meeting_ended(monkeypatch):
    integ = _mk_zoom()
    pipeline = MagicMock()
    monkeypatch.setattr(zoom_mod, 'atom_ingestion_pipeline', pipeline)
    monkeypatch.setattr(zoom_mod, 'RecordType',
                        SimpleNamespace(MEETING=SimpleNamespace(value='meeting')))
    integ.active_meetings['M1'] = zoom_meeting()
    integ._trigger_automations = AsyncMock()
    await integ._handle_meeting_ended(_evt())
    assert integ.active_meetings['M1'].status == 'ended'
    await integ._handle_meeting_ended(_evt(meeting_id='NOPE'))
    pipeline.ingest_record.side_effect = RuntimeError('lance')
    integ.active_meetings['M1'].status = 'started'
    await integ._handle_meeting_ended(_evt())
    await integ._handle_meeting_ended({'bad': 1})


async def test_zoom_handle_participant_events():
    integ = _mk_zoom()
    integ.active_meetings['M1'] = zoom_meeting()
    integ._trigger_automations = AsyncMock()
    await integ._handle_participant_joined(
        _evt(participant={'id': 'p1', 'user_name': 'Pat'}))
    assert 'p1' in integ.active_meetings['M1'].participants
    await integ._handle_participant_joined(_evt(meeting_id='NOPE',
                                               participant={'id': 'p2'}))
    await integ._handle_participant_joined({'bad': 1})
    await integ._handle_participant_left(
        _evt(participant={'id': 'p1', 'user_name': 'Pat'}))
    assert 'p1' not in integ.active_meetings['M1'].participants
    await integ._handle_participant_left(_evt(participant={'id': 'zz'}))
    await integ._handle_participant_left({'bad': 1})


async def test_zoom_handle_recording_completed(monkeypatch):
    integ = _mk_zoom()
    pipeline = MagicMock()
    monkeypatch.setattr(zoom_mod, 'atom_ingestion_pipeline', pipeline)
    monkeypatch.setattr(zoom_mod, 'RecordType',
                        SimpleNamespace(MEETING=SimpleNamespace(value='meeting')))
    integ.active_meetings['M1'] = zoom_meeting()
    integ._trigger_automations = AsyncMock()
    await integ._handle_recording_completed(
        _evt(recordings=[{'recording_length': 3600}]))
    assert integ.active_meetings['M1'].is_recorded is True
    assert integ.analytics_metrics['total_recording_hours'] == 1.0
    await integ._handle_recording_completed(_evt(meeting_id='NOPE',
                                                 recordings=[]))
    pipeline.ingest_record.side_effect = RuntimeError('lance')
    await integ._handle_recording_completed(_evt(recordings=[]))
    await integ._handle_recording_completed({'bad': 1})


async def test_zoom_trigger_automations():
    integ = _mk_zoom()
    integ.enterprise_automation = None
    await integ._trigger_automations('meeting_started', zoom_meeting(), {})
    integ.enterprise_automation = MagicMock()
    integ.automation_triggers = {
        'meeting_started': {'enabled': True},
        'other': {'enabled': True},
        'disabled_one': {'enabled': False}}
    await integ._trigger_automations('meeting_started', zoom_meeting(), {})
    assert integ.analytics_metrics['automations_triggered'] == 1


async def test_zoom_log_message_event():
    integ = _mk_zoom()
    integ.enterprise_security = None
    await integ._log_message_event('chat', 'M1', {})
    sec = MagicMock()
    sec.audit_event = AsyncMock()
    integ.enterprise_security = sec
    await integ._log_message_event('chat', 'M1', {'user_id': 'u'})
    sec.audit_event.assert_awaited_once()
    sec.audit_event = AsyncMock(side_effect=RuntimeError('x'))
    await integ._log_message_event('chat', 'M1', {})


def test_zoom_dataclasses():
    user = ZoomUser(user_id='u', email='e', first_name='a', last_name='b',
                    display_name='a b', user_type=ZoomUserType.LICENSED,
                    role='member', timezone='UTC', is_active=True,
                    permissions=[], security_level='standard', created_at=DT,
                    last_active=DT, metadata={})
    assert user.user_type == ZoomUserType.LICENSED
    evt = ZoomEvent(event_id='e', event_type=ZoomEventType.RECORDING_COMPLETED,
                    meeting_id='m', user_id='u', timestamp=DT, data={},
                    security_flags={}, compliance_flags={}, metadata={})
    assert evt.event_type.value == 'recording.completed'
    integ = zoom_mod.atom_zoom_integration
    assert integ is not None


# ============================================================================
# Teams — rate limiter
# ============================================================================

async def test_teams_rate_limiter_local():
    rl = TeamsRateLimiter()
    for _ in range(10):
        assert await rl.check_limit('w', 'files_upload') is True
    assert await rl.check_limit('w', 'files_upload') is False
    # unknown endpoint defaults to limit 10
    assert await rl.check_limit('w', 'unknown') is True
    # expired window resets
    rl.local_limits['teams_rate:w:files_upload']['reset'] = time.time() - 1
    assert await rl.check_limit('w', 'files_upload') is True


async def test_teams_rate_limiter_redis():
    redis = MagicMock()
    redis.get.return_value = '10'
    rl = TeamsRateLimiter(redis)
    assert await rl.check_limit('w', 'files_upload') is False
    redis.get.return_value = None
    assert await rl.check_limit('w', 'files_upload') is True
    redis.pipeline.return_value.incr.assert_called_once()


# ============================================================================
# Teams — token crypto, workspace storage, graph clients
# ============================================================================

def test_teams_encrypt_decrypt(teams):
    enc = teams._encrypt_token('secret-token')
    assert enc != 'secret-token'
    assert teams._decrypt_token(enc) == 'secret-token'
    teams.cipher = None
    with pytest.raises(RuntimeError):
        teams._encrypt_token('x')
    assert teams._decrypt_token('plain') == 'plain'


def test_teams_get_workspace(teams):
    teams.redis.get.return_value = None
    assert teams._get_workspace('T1') is None
    ws = mk_team_workspace('T1')
    teams.redis.get.return_value = json.dumps({
        'team_id': 'T1', 'name': 'Team', 'description': 'd',
        'display_name': 'Team', 'visibility': 'private', 'mail_nickname': 'm',
        'created_at': '2026-08-10T12:00:00+00:00', 'created_by': 'u',
        'tenant_id': 't1'})
    got = teams._get_workspace('T1')
    assert got.team_id == 'T1'
    # db path
    teams.db = MagicMock()
    teams.db.execute.return_value.fetchone.return_value = None
    assert teams._get_workspace('T2') is None
    teams.db.execute.return_value.fetchone.return_value = {
        'team_id': 'T3', 'name': 'Team', 'description': 'd',
        'display_name': 'Team', 'visibility': 'public', 'mail_nickname': 'm',
        'created_at': '2026-08-10T12:00:00+00:00', 'created_by': 'u',
        'tenant_id': 't1'}
    assert teams._get_workspace('T3').team_id == 'T3'
    teams.db.execute.side_effect = RuntimeError('db')
    assert teams._get_workspace('T4') is None


def test_teams_save_workspace(teams):
    ws = mk_team_workspace('T1', token='tok')
    assert teams._save_workspace(ws) is True
    teams.redis.setex.assert_called_once()
    assert teams.connection_status['T1'] == te_mod.TeamsConnectionStatus.CONNECTED
    # db path with token encryption
    teams.db = MagicMock()
    ws2 = mk_team_workspace('T2', token='tok')
    assert teams._save_workspace(ws2) is True
    teams.db.commit.assert_called_once()
    teams.db.execute.side_effect = RuntimeError('db')
    assert teams._save_workspace(ws2) is False


def test_teams_get_graph_client(teams, monkeypatch):
    teams.redis.get.return_value = None
    assert teams._get_graph_client('T1') is None  # no workspace
    ws = mk_team_workspace('T1')
    teams.redis.get.return_value = json.dumps(asdict_dict(ws))
    assert teams._get_graph_client('T1') is None  # no access token
    ws.access_token = teams._encrypt_token('real-token')
    teams.redis.get.return_value = json.dumps(asdict_dict(ws))
    assert teams._get_graph_client('T1') is None  # SDK unavailable
    monkeypatch.setattr(te_mod, 'GraphServiceClient', MagicMock(),
                        raising=False)
    client = teams._get_graph_client('T1')
    assert client is not None
    assert teams._get_graph_client('T1') is client  # cached
    teams.graph_clients['T2'] = 'cached-client'
    assert teams._get_graph_client('T2') == 'cached-client'
    teams.redis.get.side_effect = RuntimeError('x')
    assert teams._get_graph_client('T9') is None


def asdict_dict(ws):
    from dataclasses import asdict
    return asdict(ws, dict_factory=lambda d: {
        k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in d})


# ============================================================================
# Teams — JWKS / token verification / OAuth
# ============================================================================

def test_teams_jwks(monkeypatch):
    svc = TeamsEnhancedService.__new__(TeamsEnhancedService)
    svc.jwks_cache = {}
    svc.msal_tenant_id = 'common'
    # fresh cache
    svc.jwks_cache['teams_jwks:common'] = ([{'kid': 'k'}], time.time())
    assert svc._get_jwks_keys('common') == [{'kid': 'k'}]
    # stale cache -> refetch
    svc.jwks_cache['teams_jwks:common'] = ([], time.time() - 90000)
    resp = MagicMock()
    resp.json.return_value = {'keys': [{'kid': 'k2'}]}
    monkeypatch.setattr(te_mod.httpx, 'get', MagicMock(return_value=resp))
    assert svc._get_jwks_keys('common') == [{'kid': 'k2'}]
    # fetch error
    svc.jwks_cache.clear()
    monkeypatch.setattr(te_mod.httpx, 'get',
                        MagicMock(side_effect=RuntimeError('net')))
    assert svc._get_jwks_keys('common') is None
    # empty keys
    svc.jwks_cache.clear()
    resp2 = MagicMock()
    resp2.json.return_value = {'keys': []}
    monkeypatch.setattr(te_mod.httpx, 'get', MagicMock(return_value=resp2))
    assert svc._get_jwks_keys('common') is None


def test_teams_verify_ms_access_token(monkeypatch):
    svc = TeamsEnhancedService.__new__(TeamsEnhancedService)
    svc.jwks_cache = {}
    svc.msal_tenant_id = 'common'
    # malformed header
    with pytest.raises(ValueError):
        svc._verify_ms_access_token('not-a-jwt')
    # missing kid
    with patch.object(te_mod.jwt, 'get_unverified_header',
                      return_value={'alg': 'RS256'}):
        with pytest.raises(ValueError):
            svc._verify_ms_access_token('x.y.z')
    # JWKS unavailable
    with patch.object(te_mod.jwt, 'get_unverified_header',
                      return_value={'alg': 'RS256', 'kid': 'k1'}):
        with patch.object(svc, '_get_jwks_keys', return_value=None):
            with pytest.raises(ValueError):
                svc._verify_ms_access_token('x.y.z')
        # no matching kid
        with patch.object(svc, '_get_jwks_keys',
                          return_value=[{'kid': 'other'}]):
            with pytest.raises(ValueError):
                svc._verify_ms_access_token('x.y.z')
        # matching kid but signature verification fails
        with patch.object(svc, '_get_jwks_keys',
                          return_value=[{'kid': 'k1'}]):
            with patch.object(te_mod.jwt.algorithms.RSAAlgorithm, 'from_jwk',
                              return_value='key'):
                with patch.object(te_mod.jwt, 'decode',
                                  side_effect=te_mod.jwt.InvalidTokenError('x')):
                    with pytest.raises(ValueError):
                        svc._verify_ms_access_token('x.y.z')
                # valid decode
                with patch.object(te_mod.jwt, 'decode',
                                  return_value={'tid': 't1'}):
                    assert svc._verify_ms_access_token('x.y.z') == {'tid': 't1'}


def test_teams_generate_oauth_url(monkeypatch):
    svc = TeamsEnhancedService.__new__(TeamsEnhancedService)
    svc.msal_app = None
    svc.required_scopes = ['s1']
    svc.redirect_uri = 'https://cb'
    with pytest.raises(Exception):
        svc.generate_oauth_url('st', 'u1')
    svc.msal_app = MagicMock()
    svc.msal_app.get_authorization_request_url.return_value = 'https://login?x'
    assert 'https://login' in svc.generate_oauth_url('st', 'u1')
    assert svc.generate_oauth_url('st', 'u1', scopes=['a']) is not None


async def test_teams_exchange_code(monkeypatch):
    svc = TeamsEnhancedService.__new__(TeamsEnhancedService)
    svc.msal_app = None
    svc.required_scopes = ['s1']
    assert (await svc.exchange_code_for_tokens('c', 's'))['ok'] is False
    svc.msal_app = MagicMock()
    svc.msal_app.acquire_token_by_authorization_code.return_value = {
        'error': 'invalid_grant'}
    assert (await svc.exchange_code_for_tokens('c', 's'))['ok'] is False
    svc.msal_app.acquire_token_by_authorization_code.return_value = {
        'access_token': 'tok', 'refresh_token': 'rt'}
    with patch.object(svc, '_verify_ms_access_token',
                      return_value={'tid': 't1', 'name': 'Team',
                                    'upn': 'user@x.com', 'oid': 'o1'}):
        with patch.object(svc, '_save_workspace', return_value=True):
            res = await svc.exchange_code_for_tokens('c', 's')
            assert res['ok'] is True
        with patch.object(svc, '_save_workspace', return_value=False):
            res = await svc.exchange_code_for_tokens('c', 's')
            assert res['ok'] is False
        # verification failure -> error dict
        with patch.object(svc, '_verify_ms_access_token',
                          side_effect=ValueError('bad')):
            assert (await svc.exchange_code_for_tokens('c', 's'))['ok'] is False


# ============================================================================
# Teams — connection / workspaces / channels / messages
# ============================================================================

async def test_teams_test_connection(teams):
    assert (await teams.test_connection('T1'))['connected'] is False
    client = graph_client(teams_get=None)
    teams.graph_clients['T2'] = client
    assert (await teams.test_connection('T2'))['connected'] is False
    team = SimpleNamespace(id='T2', display_name='Team',
                           additional_data={'tenantId': 't1'},
                           visibility='private')
    client.teams.get = AsyncMock(return_value=SimpleNamespace(value=[team]))
    teams.redis.get.return_value = json.dumps(
        {'team_id': 'T2', 'name': 'Team', 'description': 'd',
         'display_name': 'Team', 'visibility': 'private', 'mail_nickname': 'm',
         'created_at': '2026-08-10T12:00:00+00:00', 'created_by': 'u',
         'tenant_id': 't1'})
    res = await teams.test_connection('T2')
    assert res['connected'] is True and res['workspace']['team_id'] == 'T2'
    client.teams.get = AsyncMock(side_effect=RuntimeError('x'))
    assert (await teams.test_connection('T2'))['status'] == 'error'


async def test_teams_get_workspaces(teams):
    teams.redis.keys.return_value = []
    assert await teams.get_workspaces() == []
    ws = {'team_id': 'T1', 'name': 'Team', 'description': 'd',
          'display_name': 'Team', 'visibility': 'private', 'mail_nickname': 'm',
          'created_at': '2026-08-10T12:00:00+00:00', 'created_by': 'u1',
          'tenant_id': 't1'}
    teams.redis.keys.return_value = ['teams_workspace:T1']
    teams.redis.get.return_value = json.dumps(ws)
    assert len(await teams.get_workspaces()) == 1
    assert len(await teams.get_workspaces(user_id='u1')) == 1
    assert await teams.get_workspaces(user_id='other') == []
    # db path
    teams.db = MagicMock()
    teams.db.execute.return_value.fetchall.return_value = [ws, ws]
    assert len(await teams.get_workspaces('u1')) == 2
    assert len(await teams.get_workspaces()) == 2
    teams.db.execute.side_effect = RuntimeError('x')
    assert await teams.get_workspaces() == []


def _channel_data(id='C1', membership='standard', archived=False):
    return SimpleNamespace(
        id=id, display_name='General', description='d',
        membership_type=membership, email='c@x.com', web_url='https://c',
        is_favorite_by_default=True, created_datetime='2026-08-10T00:00:00Z',
        last_updated_datetime='2026-08-10T01:00:00Z',
        additional_data={'memberCount': 5}, is_archived=archived,
        is_welcome_message_enabled=True, allow_cross_team_posts=True,
        allow_giphy=True, giphy_content_rating='moderate', allow_memes=True,
        allow_custom_memes=True, allow_stickers_and_gifs=True,
        allow_user_edit_messages=True, allow_owner_delete_messages=True,
        allow_team_mentions=True, allow_channel_mentions=True)


async def test_teams_get_channels(teams):
    teams.rate_limiter = MagicMock()
    teams.rate_limiter.check_limit = AsyncMock(return_value=False)
    teams.redis.get.return_value = None
    assert await teams.get_channels('T1') == []  # rate limited, no cache
    teams.rate_limiter.check_limit = AsyncMock(return_value=True)
    assert (await teams.get_channels('T1')) == []  # no graph client
    # graph client with channel mix
    client = graph_client(channels_get=SimpleNamespace(
        value=[_channel_data('C1'),
               _channel_data('C2', membership='private'),
               _channel_data('C3', archived=True)]))
    teams.graph_clients['T1'] = client
    chans = await teams.get_channels('T1', include_private=True)
    assert len(chans) == 2  # private included, archived excluded
    assert chans[0].channel_id == 'C1'
    # error path with cached fallback
    client.teams.__getitem__.return_value.channels.get = AsyncMock(
        side_effect=RuntimeError('x'))
    teams.redis.get.return_value = json.dumps([asdict_dict(
        TeamsChannel(channel_id='CX', name='n', display_name='n',
                     description='d', workspace_id='T1', channel_type='standard'))])
    chans = await teams.get_channels('T1')
    assert chans[0].channel_id == 'CX'


async def test_teams_send_message(teams):
    teams.rate_limiter = MagicMock()
    teams.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await teams.send_message('T1', 'C1', 'hi'))['ok'] is False
    teams.rate_limiter.check_limit = AsyncMock(return_value=True)
    assert (await teams.send_message('T1', 'C1', 'hi'))['ok'] is False  # no client
    result = SimpleNamespace(id='m1', created_datetime='2026-08-10T00:00:00Z')
    client = graph_client(messages_post=result)
    teams.graph_clients['T1'] = client
    res = await teams.send_message('T1', 'C1', '<b>hello</b>',
                                   importance='high', subject='s',
                                   attachments=[{'a': 1}])
    assert res['ok'] is True and res['message_id'] == 'm1'
    res = await teams.send_message('T1', 'C1', 'plain', thread_id='t1')
    assert res['ok'] is True
    client.teams.__getitem__.return_value.channels.__getitem__.return_value\
        .messages.post = AsyncMock(return_value=None)
    assert (await teams.send_message('T1', 'C1', 'x'))['ok'] is False


def _msg_data(id='m1'):
    sender = SimpleNamespace(additional_data={'user': {
        'id': 'u1', 'displayName': 'Alice', 'emailAddress': 'a@x.com'}})
    return SimpleNamespace(
        id=id, body=SimpleNamespace(content='<p>hi</p>'),
        **{'from': sender}, created_datetime='2026-08-10T00:00:00Z',
        reply_to_id=None, message_type='message', importance='normal',
        subject=None, summary=None, attachments=[], mentions=[],
        last_modified_datetime='2026-08-10T01:00:00Z', etag='e',
        channel_identity={'channelId': 'C1'},
        additional_data={'participantCount': 2}, localized={})


async def test_teams_get_channel_messages(teams):
    teams.rate_limiter = MagicMock()
    teams.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert await teams.get_channel_messages('T1', 'C1') == []
    teams.rate_limiter.check_limit = AsyncMock(return_value=True)
    assert await teams.get_channel_messages('T1', 'C1') == []  # no client
    client = graph_client(
        messages_get=SimpleNamespace(value=[_msg_data(), _msg_data('m2')]))
    teams.graph_clients['T1'] = client
    msgs = await teams.get_channel_messages('T1', 'C1', limit=10,
                                            latest='L', oldest='O')
    assert len(msgs) == 2 and msgs[0].user_id == 'u1'
    assert msgs[0].is_edited is True
    # exception + cached fallback
    client.teams.__getitem__.return_value.channels.__getitem__.return_value\
        .messages.get = AsyncMock(side_effect=RuntimeError('x'))
    teams.redis.get.return_value = json.dumps([{
        'message_id': 'mX', 'text': 't', 'user_id': 'u', 'user_name': 'n',
        'user_email': 'e', 'channel_id': 'C1', 'workspace_id': 'T1',
        'tenant_id': 't', 'timestamp': 'ts'}])
    msgs = await teams.get_channel_messages('T1', 'C1')
    assert msgs[0].message_id == 'mX'


async def test_teams_search_messages(teams, monkeypatch):
    teams.rate_limiter = MagicMock()
    teams.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await teams.search_messages('T1', 'q'))['ok'] is False
    teams.rate_limiter.check_limit = AsyncMock(return_value=True)
    assert (await teams.search_messages('T1', 'q'))['ok'] is False  # no client
    teams.graph_clients['T1'] = graph_client()
    payload = {'value': [{'hitsContainers': [{'hits': [
        {'resource': {'id': 'm1', 'body': {'content': 'x'},
                      'from': {'id': 'u', 'displayName': 'n'},
                      'channelIdentity': {'channelId': 'C1'},
                      'createdDateTime': 't', 'lastModifiedDateTime': 't2'}}],
        'total': 1}]}]}
    resp = _resp(200, payload)
    cls = MagicMock()
    cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
    monkeypatch.setattr(te_mod.httpx, 'AsyncClient', cls)
    res = await teams.search_messages('T1', 'q"uery"', channel_id='C1',
                                      user_id='u1')
    assert res['ok'] is True and res['total'] == 1
    body = cls.return_value.__aenter__.return_value.post.await_args.kwargs['json']
    assert '""' in body['requests'][0]['query']['queryString']  # KQL escape
    # API error
    resp.status_code = 500
    res = await teams.search_messages('T1', 'q')
    assert res['ok'] is False


async def test_teams_upload_file(teams, tmp_path, monkeypatch):
    f = tmp_path / 'doc.pdf'
    f.write_bytes(b'pdf')
    teams.rate_limiter = MagicMock()
    teams.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await teams.upload_file('T1', 'C1', str(f)))['ok'] is False
    teams.rate_limiter.check_limit = AsyncMock(return_value=True)
    assert (await teams.upload_file('T1', 'C1', str(f)))['ok'] is False  # no client
    client = graph_client()
    client.teams.__getitem__.return_value.get = AsyncMock(return_value=SimpleNamespace(
        additional_data={'siteId': 'site-team'}))
    teams.graph_clients['T1'] = client
    teams.send_message = AsyncMock(return_value={'ok': True})
    upload_resp = _resp(201, {
        'id': 'f1', 'name': 'doc.pdf', 'size': 3,
        'createdDateTime': '2026-08-10T00:00:00Z',
        'webUrl': 'https://f', '@microsoft.graph.downloadUrl': 'https://d',
        'file': {'mimeType': 'application/pdf'}})
    cls = MagicMock()
    cls.return_value.__aenter__.return_value.put = AsyncMock(
        return_value=upload_resp)
    monkeypatch.setattr(te_mod.httpx, 'AsyncClient', cls)
    res = await teams.upload_file('T1', 'C1', str(f), title='My doc')
    assert res['ok'] is True and res['file']['is_document'] is True
    teams.send_message.assert_awaited_once()
    # upload failure
    upload_resp.status_code = 500
    assert (await teams.upload_file('T1', 'C1', str(f)))['ok'] is False


# ============================================================================
# Teams — info / operations / sync / close
# ============================================================================

async def test_teams_info_capabilities_health(teams):
    info = await teams.get_service_info()
    assert info['name'] == 'Microsoft Teams Enhanced Service'
    caps = teams.get_capabilities()
    assert len(caps['operations']) == 4
    teams.client_id = 'cid'
    teams.client_secret = None
    assert teams.health_check()['ok'] is False
    teams.client_secret = 'sec'
    assert teams.health_check()['ok'] is True


async def test_teams_execute_operation(teams, monkeypatch):
    teams.send_message = AsyncMock(return_value={'ok': True})
    res = await teams.execute_operation(
        'send_message', {'workspace_id': 'T1', 'channel_id': 'C1', 'text': 'hi'})
    assert res['success'] is True
    # tenant mismatch
    res = await teams.execute_operation(
        'send_message', {'workspace_id': 'T', 'channel_id': 'C', 'text': 'x'},
        context={'tenant_id': 'other'})
    assert res['error'] == 'Tenant mismatch'
    # other ops
    teams.get_channel_messages = AsyncMock(return_value=[
        TeamsMessage(message_id='m', text='t', user_id='u', user_name='n',
                     user_email='e', channel_id='c', workspace_id='w',
                     tenant_id='t', timestamp='ts')])
    assert (await teams.execute_operation(
        'get_channel_messages', {'workspace_id': 'T1', 'channel_id': 'C1'}))['success']
    teams.get_channels = AsyncMock(return_value=[])
    assert (await teams.execute_operation(
        'list_channels', {'workspace_id': 'T1'}))['success']
    teams.search_messages = AsyncMock(return_value={'ok': True})
    assert (await teams.execute_operation(
        'search_messages', {'workspace_id': 'T1', 'query': 'q'}))['success']
    assert (await teams.execute_operation('bogus', {}))['success'] is False
    teams.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await teams.execute_operation(
        'send_message', {'workspace_id': 'T', 'channel_id': 'C',
                         'text': 'x'}))['success'] is False


async def test_teams_sync_to_postgres_cache(teams, monkeypatch):
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    session_local = MagicMock(return_value=session)
    metric_model = MagicMock()
    monkeypatch.setattr('core.database.SessionLocal', session_local)
    import core.database as core_db
    monkeypatch.setattr(core_db, 'SessionLocal', session_local)
    import core.models as core_models
    monkeypatch.setattr(core_models, 'IntegrationMetric', metric_model,
                        raising=False)
    teams.get_channels = AsyncMock(return_value=[
        TeamsChannel(channel_id='C', name='n', display_name='n', description='',
                     workspace_id='T1', channel_type='standard',
                     message_count=7)])
    teams._get_workspace = lambda wid: mk_team_workspace('T1')
    res = await teams.sync_to_postgres_cache('T1')
    assert res['success'] is True and res['metrics_synced'] == 3
    session.commit.assert_called_once()
    # db save failure
    session.commit.side_effect = RuntimeError('pg')
    res = await teams.sync_to_postgres_cache('T1')
    assert res['success'] is False
    session.rollback.assert_called_once()
    # import failure
    def boom(name):
        raise ImportError('no module')
    original_import = __import__

    def fake_import(name, *a, **k):
        if name in ('core.database', 'core.models'):
            raise ImportError(name)
        return original_import(name, *a, **k)
    with patch('builtins.__import__', side_effect=fake_import):
        res = await teams.sync_to_postgres_cache('T1')
        assert res['success'] is False


async def test_teams_full_sync_and_close(teams):
    teams.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 3})
    res = await teams.full_sync('T1')
    assert res['success'] is True and res['workspace_id'] == 'T1'
    teams.graph_clients['x'] = 1
    await teams.close()
    assert teams.graph_clients == {}
    teams.redis.close.assert_called_once()


def test_teams_channel_and_message_models():
    ch = TeamsChannel(channel_id='C', name='n', display_name='n',
                      description='d', workspace_id='T', channel_type='standard')
    assert ch.created_at is not None
    msg = TeamsMessage(message_id='m', text='t', user_id='u',
                              user_name='n', user_email='e', channel_id='c',
                              workspace_id='w', tenant_id='t', timestamp='ts')
    assert msg.attachments == [] and msg.localized == {}
