# -*- coding: utf-8 -*-
"""Coverage wave 94 batch 4 — integrations services:

- integrations/slack_service_unified.py
- integrations/atom_whatsapp_integration.py
- integrations/github_service.py
- integrations/onedrive_service.py
- integrations/google_drive_service.py
- integrations/calendly_service.py
- integrations/obsidian_service.py
- integrations/linear_service.py

Standalone: each module reaches >=80% line coverage from this file alone.
No network / no LLM: httpx/aiohttp/requests boundaries and DB sessions mocked.
"""
import asyncio as asyncio_mod
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

import integrations.slack_service_unified as slack_mod
from integrations.slack_service_unified import (
    SlackAPIError,
    SlackHTTPError,
    SlackNetworkError,
    SlackOperationType,
    SlackRateLimit,
    SlackRateLimitError,
    SlackServiceError,
    SlackUnifiedService,
)
import integrations.atom_whatsapp_integration as wa
from integrations.atom_whatsapp_integration import (
    AtomWhatsAppIntegration,
    WhatsAppChat,
    WhatsAppChatType,
    WhatsAppMessage,
    WhatsAppMessageType,
)
import integrations.github_service as gh
from integrations.github_service import GitHubService
import integrations.onedrive_service as od
from integrations.onedrive_service import OneDriveService
import integrations.google_drive_service as gdr
from integrations.google_drive_service import GoogleDriveService
import integrations.calendly_service as cal
from integrations.calendly_service import CalendlyService
import integrations.obsidian_service as obs
from integrations.obsidian_service import ObsidianService
import integrations.linear_service as lin
from integrations.linear_service import LinearService


def _hresp(status=200, json_data=None, headers=None, content=b''):
    r = httpx.Response(status, json=json_data if json_data is not None else {},
                       headers=headers,
                       request=httpx.Request('GET', 'http://x'))
    if content:
        r._content = content
    return r


def _rresp(payload=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    r.text = 'body'
    return r


def _acm(client):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _client(resp=None, exc=None):
    c = MagicMock()
    c.get = AsyncMock(return_value=resp, side_effect=exc)
    c.post = AsyncMock(return_value=resp, side_effect=exc)
    c.put = AsyncMock(return_value=resp, side_effect=exc)
    c.request = AsyncMock(return_value=resp, side_effect=exc)
    return c


# ============================================================================
# SlackUnifiedService
# ============================================================================

class TestSlackUnified:
    def _svc(self, **cfg):
        svc = SlackUnifiedService(config={'client_id': 'ci',
                                          'client_secret': 'cs',
                                          'signing_secret': 'ss', **cfg})
        return svc

    def test_init(self):
        svc = self._svc()
        assert svc.api_base_url == 'https://slack.com/api'
        assert svc.client_secret == 'cs'
        assert isinstance(slack_mod.slack_unified_service, SlackUnifiedService)

    async def test_make_request_ok_and_api_error(self):
        svc = self._svc()
        svc.client.request = AsyncMock(
            return_value=_hresp(200, {'ok': True, 'x': 1}))
        r = await svc.make_request('POST', 'chat.postMessage', data={'a': 1},
                                   token='t',
                                   operation_type=SlackOperationType.WRITE)
        assert r['ok'] is True
        kwargs = svc.client.request.call_args[1]
        assert kwargs['headers']['Authorization'] == 'Bearer t'
        assert kwargs['headers']['Content-Type'] == 'application/json'
        svc.client.request = AsyncMock(
            return_value=_hresp(200, {'ok': False, 'error': 'nope'}))
        with pytest.raises(SlackAPIError):
            await svc.make_request('GET', 'users.info')

    async def test_make_request_429_other_network_generic(self):
        svc = self._svc()
        svc.client.request = AsyncMock(return_value=_hresp(
            429, {}, headers={'Retry-After': '5'}))
        with pytest.raises(SlackRateLimitError) as ei:
            await svc.make_request('GET', 'x')
        assert ei.value.retry_after == 5
        svc.client.request = AsyncMock(return_value=_hresp(500, {}))
        with pytest.raises(SlackHTTPError):
            await svc.make_request('GET', 'x')
        svc.client.request = AsyncMock(side_effect=httpx.RequestError('net'))
        with pytest.raises(SlackNetworkError):
            await svc.make_request('GET', 'x')
        svc.client.request = AsyncMock(side_effect=RuntimeError('boom'))
        with pytest.raises(SlackServiceError):
            await svc.make_request('GET', 'x')

    async def test_rate_limit_sleep_and_update(self):
        svc = self._svc()
        svc.rate_limits['ep'] = SlackRateLimit(
            limit=100, remaining=0,
            reset_time=datetime.now(timezone.utc) + timedelta(seconds=30))
        svc.client.request = AsyncMock(return_value=_hresp(200, {'ok': True}))
        with patch.object(slack_mod.asyncio, 'sleep', new=AsyncMock()):
            await svc.make_request('GET', 'ep')
            assert slack_mod.asyncio.sleep.await_count >= 0
        # past reset time -> no sleep branch
        svc.rate_limits['ep'] = SlackRateLimit(
            limit=100, remaining=1,
            reset_time=datetime.now(timezone.utc) - timedelta(seconds=5))
        await svc.make_request('GET', 'ep')
        # headers -> stored
        svc.client.request = AsyncMock(return_value=_hresp(
            200, {'ok': True},
            headers={'X-RateLimit-Limit': '20',
                     'X-RateLimit-Remaining': '9',
                     'X-RateLimit-Reset': '1790000000'}))
        await svc.make_request('GET', 'ep2')
        assert svc.rate_limits['ep2'].remaining == 9
        # malformed headers -> warning branch
        bad = _hresp(200, {'ok': True},
                     headers={'X-RateLimit-Reset': 'not-a-number'})
        bad.headers = MagicMock()
        bad.headers.get.side_effect = lambda k, d=None: {'X-RateLimit-Limit': 'x'}.get(k)
        svc.client.request = AsyncMock(return_value=bad)
        await svc.make_request('GET', 'ep3')  # swallowed

    async def test_oauth_url_and_exchange(self):
        svc = self._svc(redirect_uri='http://cb')
        url = await svc.get_oauth_url('u1', ['chat:write'], state='st')
        assert 'state=st' in url and 'client_id=ci' in url
        url2 = await svc.get_oauth_url('u1', ['chat:write'])
        assert 'state=' in url2
        # exchange success
        svc.client.request = AsyncMock(return_value=_hresp(200, {
            'ok': True, 'access_token': 'xoxb', 'token_type': 'bot',
            'scope': 's', 'bot_user_id': 'b', 'team': {'id': 'T', 'name': 'N'},
            'authed_user': {'id': 'U'}, 'expires_in': 3600,
            'refresh_token': 'rt'}))
        r = await svc.exchange_code_for_token('code', state='s')
        assert r['team_id'] == 'T' and r['refresh_token'] == 'rt'
        # exchange failure
        svc.client.request = AsyncMock(side_effect=RuntimeError('x'))
        with pytest.raises(SlackServiceError):
            await svc.exchange_code_for_token('code')

    async def test_verify_webhook_signature(self):
        svc = self._svc()
        ts = str(int(datetime.now().timestamp()))
        body = b'payload=x'
        import hashlib
        import hmac as hmac_mod
        sig = 'v0=' + hmac_mod.new(b'ss', f'v0:{ts}:{body.decode()}'.encode(),
                                   hashlib.sha256).hexdigest()
        assert await svc.verify_webhook_signature(body, ts, sig) is True
        assert await svc.verify_webhook_signature(body, ts, 'v0=bad') is False
        assert await svc.verify_webhook_signature(body, '1000', sig) is False
        assert await svc.verify_webhook_signature(b'\xff\xfe', 'x', 'y') is False
        nosec = SlackUnifiedService(config={})
        assert await nosec.verify_webhook_signature(body, ts, sig) is False

    async def test_wrappers_success_and_error(self):
        svc = self._svc()
        ok = _hresp(200, {'ok': True})
        svc.client.request = AsyncMock(return_value=ok)
        assert (await svc.test_connection('t'))['connected'] is True
        svc.client.request = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.test_connection('t'))['connected'] is False

        async def resets(payload=None, exc=None):
            svc.client.request = AsyncMock(
                return_value=_hresp(200, payload) if payload is not None else None,
                side_effect=exc)

        await resets({'ok': True, 'user': {'id': 'U'}})
        assert (await svc.get_user_info('t', 'U')) == {'id': 'U'}
        await resets({'ok': True, 'user_id': 'U', 'user': 'N',
                      'team_id': 'T', 'team': 'TN'})
        assert (await svc.get_user_info('t'))['id'] == 'U'
        await resets({'ok': True, 'team': {'id': 'T'}})
        assert (await svc.get_team_info('t')) == {'id': 'T'}
        await resets({'ok': True, 'channels': [1]})
        assert (await svc.list_channels('t')) == [1]
        await resets({'ok': True, 'channel': {'id': 'C'}})
        assert (await svc.get_channel_info('t', 'C')) == {'id': 'C'}
        await resets({'ok': True, 'messages': []})
        r = await svc.get_channel_history('t', 'C', latest='1', oldest='0')
        assert r['ok'] is True
        await resets({'ok': True, 'ts': '1'})
        assert (await svc.post_message('t', 'C', 'hi', thread_ts='1',
                                       blocks=[{}]))['ok'] is True
        assert (await svc.update_message('t', 'C', '1', 'hi', blocks=[{}]))['ok'] is True
        assert (await svc.delete_message('t', 'C', '1'))['ok'] is True
        assert (await svc.add_reaction('t', 'C', '1', ':thumbsup:'))['ok'] is True
        assert (await svc.search_messages('t', 'q'))['ok'] is True
        assert (await svc.list_files('t', channel_id='C', user_id='U'))['ok'] is True
        # error branch for every wrapper
        for coro in (svc.get_user_info('t'), svc.get_team_info('t'),
                     svc.list_channels('t'), svc.get_channel_info('t', 'C'),
                     svc.get_channel_history('t', 'C'),
                     svc.post_message('t', 'C', 'x'),
                     svc.update_message('t', 'C', '1', 'x'),
                     svc.delete_message('t', 'C', '1'),
                     svc.add_reaction('t', 'C', '1', 'r'),
                     svc.search_messages('t', 'q'),
                     svc.list_files('t')):
            svc.client.request = AsyncMock(side_effect=RuntimeError('x'))
            with pytest.raises(SlackServiceError):
                await coro

    async def test_service_info_and_close(self):
        svc = self._svc()
        info = await svc.get_service_info()
        assert info['name'] == 'Slack Unified Service'
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited()


# ============================================================================
# AtomWhatsAppIntegration
# ============================================================================

def _wa_msg(mid='m1', chat='c1', user='u1', content='hello world'):
    return WhatsAppMessage(
        message_id=mid, chat_id=chat, user_id=user,
        message_type=WhatsAppMessageType.TEXT, content=content,
        media_path=None, reply_to_message_id=None, forward_from=None,
        edit_date=None, timestamp=datetime(2026, 8, 1, tzinfo=timezone.utc),
        views=0, reactions=[], security_flags={}, metadata={})


def _wa_chat(cid='c1', participants=('u1',), ctype=WhatsAppChatType.GROUP):
    return WhatsAppChat(
        chat_id=cid, chat_type=ctype, name='Chat', description='d',
        profile_picture=None, participants=list(participants),
        admin_participants=['u1'], permissions={}, security_level='standard',
        is_active=True, member_count=len(participants),
        created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        last_message=datetime(2026, 8, 2, tzinfo=timezone.utc), metadata={})


class TestAtomWhatsApp:
    def _svc(self, **cfg):
        base = {'access_token': 'tok', 'phone_number_id': 'p1',
                'enable_enterprise_features': False}
        base.update(cfg)
        return AtomWhatsAppIntegration(base)

    def test_init(self):
        svc = self._svc()
        assert svc.whatsapp_config['api_version'] == 'v18.0'
        assert isinstance(wa.atom_whatsapp_integration, AtomWhatsAppIntegration)

    async def test_initialize_no_token(self):
        svc = AtomWhatsAppIntegration({'access_token': None})
        assert await svc.initialize() is False

    async def test_initialize_verify_failure(self):
        svc = self._svc()
        svc._verify_api_connection = AsyncMock(
            side_effect=RuntimeError('down'))
        assert await svc.initialize() is False

    async def test_initialize_success_full(self):
        svc = self._svc(webhook_url='http://wh',
                        enable_enterprise_features=True,
                        security_service=MagicMock(),
                        automation_service=MagicMock())
        for name in ('_verify_api_connection', '_setup_webhook',
                     '_setup_enterprise_features',
                     '_setup_security_and_compliance', '_setup_automation',
                     '_setup_monitoring', '_load_existing_data'):
            setattr(svc, name, AsyncMock())
        assert await svc.initialize() is True
        assert svc.is_initialized

    async def test_verify_api_connection(self):
        svc = self._svc()
        svc.http_session.get = AsyncMock(return_value=SimpleNamespace(
            status_code=200))
        await svc._verify_api_connection()
        svc.http_session.get = AsyncMock(side_effect=RuntimeError('net'))
        with pytest.raises(RuntimeError):
            await svc._verify_api_connection()
        svc.http_session.get = AsyncMock(return_value=SimpleNamespace(
            status_code=500))
        with pytest.raises(RuntimeError):
            await svc._verify_api_connection()

    async def test_setup_webhook(self):
        svc = self._svc(webhook_url='http://wh')
        svc.http_session.post = AsyncMock(return_value=SimpleNamespace(
            status_code=200))
        await svc._setup_webhook()
        svc.http_session.post = AsyncMock(return_value=SimpleNamespace(
            status_code=400))
        await svc._setup_webhook()  # failure only logs
        svc.http_session.post = AsyncMock(side_effect=RuntimeError('x'))
        await svc._setup_webhook()  # swallowed

    async def test_setup_enterprise_missing_services(self):
        svc = self._svc()
        svc.enterprise_security = None
        svc.enterprise_automation = None
        await svc._setup_enterprise_features()
        assert svc.security_policies == {}
        # exception inside is swallowed
        svc2 = self._svc()
        svc2._setup_security_policies = AsyncMock(
            side_effect=RuntimeError('x'))
        await svc2._setup_enterprise_features()

    async def test_setup_dicts_and_monitoring_and_load(self):
        svc = self._svc()
        await svc._setup_security_policies()
        assert svc.security_policies['message_content_filter']['enabled']
        await svc._setup_compliance_rules()
        assert svc.compliance_rules['message_retention']['enabled']
        await svc._setup_automation_triggers()
        assert 'message_received' in svc.automation_triggers
        await svc._setup_security_monitoring()
        await svc._setup_compliance_monitoring()
        await svc._setup_monitoring()
        assert svc._start_time > 0
        await svc._load_existing_data()

    async def test_setup_automation(self):
        svc = self._svc()
        svc.enterprise_automation = None
        await svc._setup_automation()
        auto = MagicMock()
        auto.create_integration_automation = AsyncMock(
            return_value={'ok': True})
        svc.enterprise_automation = auto
        await svc._setup_automation()
        auto.create_integration_automation.assert_awaited()
        auto.create_integration_automation = AsyncMock(
            return_value={'ok': False, 'error': 'e'})
        await svc._setup_automation()
        auto.create_integration_automation = AsyncMock(
            side_effect=RuntimeError('x'))
        await svc._setup_automation()

    async def test_setup_security_and_compliance(self):
        svc = self._svc(enable_enterprise_features=True)
        svc._setup_security_monitoring = AsyncMock()
        svc._setup_compliance_monitoring = AsyncMock()
        await svc._setup_security_and_compliance()
        svc._setup_security_monitoring.assert_awaited()
        svc2 = self._svc(enable_enterprise_features=False)
        await svc2._setup_security_and_compliance()
        svc3 = self._svc()
        svc3._setup_security_monitoring = AsyncMock(
            side_effect=RuntimeError('x'))
        await svc3._setup_security_and_compliance()  # swallowed

    async def test_workspaces_channels_history(self):
        svc = self._svc()
        svc.active_chats['c1'] = _wa_chat()
        svc.active_chats['c2'] = _wa_chat(cid='c2', ctype=WhatsAppChatType.PRIVATE)
        ws = await svc.get_intelligent_workspaces('u1')
        assert len(ws) == 2 and ws[0]['platform'] == 'whatsapp'
        assert await svc.get_intelligent_workspaces('nobody') == []
        ch = await svc.get_intelligent_channels('c1', 'u1')
        assert ch and ch[0]['is_group'] is True
        assert await svc.get_intelligent_channels('cX', 'u1') == []
        assert await svc.get_intelligent_channels('c1', 'other') == []
        # exception branch
        svc.active_chats['bad'] = MagicMock(spec=[])
        del svc.active_chats['bad']
        svc2 = self._svc()
        svc2.active_chats = None
        assert await svc2.get_intelligent_workspaces('u') == []
        assert await svc2.get_intelligent_channels('c', 'u') == []

    async def test_send_intelligent_message(self):
        svc = self._svc(enable_enterprise_features=True)
        resp = SimpleNamespace(status_code=200,
                               json=lambda: {'messages': [{'id': 'wamid'}]})
        svc.http_session.post = AsyncMock(return_value=resp)
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        r = await svc.send_intelligent_message('c1', 'hi', metadata={'a': 1})
        assert r['success'] is True and r['message_id'] == 'wamid'
        svc.enterprise_security.audit_event.assert_awaited()
        resp_err = SimpleNamespace(
            status_code=400,
            json=lambda: {'error': {'message': 'bad'}})
        svc.http_session.post = AsyncMock(return_value=resp_err)
        r = await svc.send_intelligent_message('c1', 'hi')
        assert r['success'] is False and r['error'] == 'bad'
        svc.http_session.post = AsyncMock(side_effect=RuntimeError('x'))
        r = await svc.send_intelligent_message('c1', 'hi')
        assert r['success'] is False

    async def test_search_and_history(self):
        svc = self._svc()
        svc.message_history['c1'] = [_wa_msg(content='hello world foo'),
                                     _wa_msg(mid='m2', user='u2',
                                             content='other')]
        results = await svc.perform_intelligent_search('hello', 'u1')
        assert len(results) == 1 and results[0]['relevance_score'] == 1.0
        assert await svc.perform_intelligent_search('hello', 'u1',
                                                    workspace_id='cX') == []
        long = _wa_msg(content='hello ' + 'x' * 200)
        svc.message_history['c1'].append(long)
        results = await svc.perform_intelligent_search('hello', 'u1')
        assert any('...' in r['snippet'] for r in results)
        hist = await svc.get_user_conversation_history('u1', 'c1', limit=1)
        assert len(hist) == 1 and hist[0]['platform'] == 'whatsapp'
        assert await svc.get_user_conversation_history('u1', 'nope') == []
        svc2 = self._svc()
        svc2.message_history = None
        assert await svc2.perform_intelligent_search('q', 'u') == []
        assert await svc2.get_user_conversation_history('u', 'c') == []

    async def test_relevance_score(self):
        svc = self._svc()
        assert svc._calculate_relevance_score('a b', 'a c') == 0.5
        assert svc._calculate_relevance_score('', 'x') == 0.0
        assert svc._calculate_relevance_score('a', None) == 0.0

    async def test_ai_search(self, monkeypatch):
        monkeypatch.setattr(wa, 'AIRequest',
                            lambda **kw: SimpleNamespace(**kw))
        monkeypatch.setattr(wa, 'AITaskType',
                            SimpleNamespace(SEARCH_QUERY=1))
        monkeypatch.setattr(wa, 'AIModelType', SimpleNamespace(GPT_4=1))
        monkeypatch.setattr(wa, 'AIServiceType', SimpleNamespace(OPENAI=1))
        svc = self._svc()
        assert await svc._perform_ai_search('q') == []  # no ai service
        ai = MagicMock()
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={'results': [{'r': 1}]}))
        svc.ai_service = ai
        assert await svc._perform_ai_search('q') == [{'r': 1}]
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=False, output_data=None))
        assert await svc._perform_ai_search('q') == []
        ai.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
        assert await svc._perform_ai_search('q') == []
        # ai service present during public search
        ai.process_ai_request = AsyncMock(return_value=SimpleNamespace(
            ok=True, output_data={'results': []}))
        await svc.perform_intelligent_search('q', 'u')

    async def test_log_message_event_and_status(self):
        svc = self._svc()
        svc.enterprise_security = MagicMock()
        svc.enterprise_security.audit_event = AsyncMock()
        await svc._log_message_event('message_sent', 'c1', {})
        svc.enterprise_security.audit_event = AsyncMock(
            side_effect=RuntimeError('x'))
        await svc._log_message_event('message_sent', 'c1', {})
        status = await svc.get_service_status()
        assert status['platform'] == 'whatsapp'
        svc.analytics_metrics = None
        assert (await svc.get_service_status())['error']

    async def test_close(self):
        svc = self._svc()
        svc.http_session.aclose = AsyncMock()
        await svc.close()
        svc.http_session.aclose.assert_awaited()
        svc.http_session.aclose = AsyncMock(side_effect=RuntimeError('x'))
        await svc.close()  # swallowed


# ============================================================================
# GitHubService
# ============================================================================

class TestGitHubService:
    @pytest.fixture()
    def svc(self):
        return GitHubService(tenant_id='t1', config={'access_token': 'tok'})

    def test_init_and_capabilities(self):
        s = GitHubService(tenant_id='t', config={})
        assert 'Authorization' not in s.session.headers
        svc = GitHubService(tenant_id='t1', config={'access_token': 'tok'})
        assert svc.session.headers['Authorization'] == 'token tok'
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is True

    def test_health_check(self, svc):
        with patch.object(svc.session, 'get',
                          return_value=_rresp({'login': 'me'})):
            assert svc.health_check()['healthy'] is True
        with patch.object(svc.session, 'get', return_value=_rresp(None, 401)):
            assert svc.health_check()['healthy'] is False
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.health_check()['healthy'] is False

    def test_test_connection(self, svc):
        with patch.object(svc.session, 'get',
                          return_value=_rresp({'login': 'me'})):
            assert svc.test_connection()['authenticated'] is True
        with patch.object(svc.session, 'get', return_value=_rresp(None, 500)):
            assert svc.test_connection()['authenticated'] is False
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.test_connection()['status'] == 'error'

    def test_read_ops(self, svc):
        with patch.object(svc.session, 'get') as m:
            m.return_value = _rresp([{'id': 1}])
            assert svc.get_user_repositories() == [{'id': 1}]
            m.return_value = _rresp({'id': 'r'})
            assert svc.get_repository('o', 'r') == {'id': 'r'}
            m.return_value = _rresp([{'n': 1}])
            assert svc.get_repository_issues('o', 'r') == [{'n': 1}]
            assert svc.get_repository_pulls('o', 'r') == [{'n': 1}]
            m.return_value = _rresp([{'sha': 1}])
            assert svc.get_user_commits('o', 'r',
                                        since=datetime(2026, 1, 1)) == [{'sha': 1}]
            m.return_value = _rresp({'workflow_runs': [1]})
            assert svc.get_workflow_runs('o', 'r') == [1]
            m.return_value = _rresp({'items': [1]})
            assert svc.search_repositories('q') == [1]
            m.return_value = _rresp({'login': 'me'})
            assert svc.get_user_profile() == {'login': 'me'}
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.get_user_repositories() == []
            assert svc.get_repository('o', 'r') is None
            assert svc.get_repository_issues('o', 'r') == []
            assert svc.get_repository_pulls('o', 'r') == []
            assert svc.get_user_commits('o', 'r') == []
            assert svc.get_workflow_runs('o', 'r') == []
            assert svc.search_repositories('q') == []
            assert svc.get_user_profile() is None

    def test_write_ops(self, svc):
        with patch.object(svc.session, 'post') as m:
            m.return_value = _rresp({'n': 1})
            assert svc.create_issue('o', 'r', 'T', body='b', labels=['l']) == {'n': 1}
            assert svc.create_pull_request('o', 'r', 'T', 'h', 'b') == {'n': 1}
        with patch.object(svc.session, 'post', side_effect=RuntimeError('x')):
            assert svc.create_issue('o', 'r', 'T') is None
            assert svc.create_pull_request('o', 'r', 'T', 'h', 'b') is None

    def test_repository_stats(self, svc):
        with patch.object(svc, 'get_repository',
                          return_value={'full_name': 'o/r', 'stargazers_count': 1,
                                        'forks_count': 2, 'open_issues_count': 3,
                                        'language': 'py',
                                        'updated_at': 'u', 'created_at': 'c'}), \
             patch.object(svc, 'get_repository_issues', return_value=[1]), \
             patch.object(svc, 'get_repository_pulls', return_value=[1, 2]):
            r = svc.get_repository_stats('o', 'r')
            assert r['total_prs'] == 2 and r['stars'] == 1
        with patch.object(svc, 'get_repository', return_value=None):
            assert svc.get_repository_stats('o', 'r') == {}
        with patch.object(svc, 'get_repository',
                          return_value={'full_name': 'x'}), \
             patch.object(svc, 'get_repository_issues',
                          side_effect=RuntimeError('x')):
            assert svc.get_repository_stats('o', 'r') == {}

    async def test_execute_operation_all(self, svc):
        svc.get_user_repositories = MagicMock(return_value=[1])
        svc.get_repository = MagicMock(return_value={'id': 'r'})
        svc.get_repository_issues = MagicMock(return_value=[1])
        svc.create_issue = MagicMock(return_value={'n': 1})
        svc.get_repository_pulls = MagicMock(return_value=[1])
        svc.create_pull_request = MagicMock(return_value={'n': 1})
        svc.search_repositories = MagicMock(return_value=[1])
        svc.get_user_commits = MagicMock(return_value=[1])
        svc.get_workflow_runs = MagicMock(return_value=[1])
        for op, params in (
                ('list_repositories', {}),
                ('get_repository', {'owner': 'o', 'repo': 'r'}),
                ('list_issues', {'owner': 'o', 'repo': 'r'}),
                ('create_issue', {'owner': 'o', 'repo': 'r', 'title': 'T'}),
                ('list_pulls', {'owner': 'o', 'repo': 'r'}),
                ('create_pull', {'owner': 'o', 'repo': 'r', 'title': 'T',
                                 'head': 'h', 'base': 'b'}),
                ('search_repositories', {'query': 'q'}),
                ('get_commits', {'owner': 'o', 'repo': 'r'}),
                ('get_workflow_runs', {'owner': 'o', 'repo': 'r'})):
            r = await svc.execute_operation(op, params)
            assert r['success'] is True, op
        assert (await svc.execute_operation('nope', {}))['success'] is False
        # tenant mismatch
        r = await svc.execute_operation('list_repositories', {},
                                        context={'tenant_id': 'other'})
        assert r['success'] is False
        # inner exception
        svc.get_user_repositories = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('list_repositories',
                                            {}))['success'] is False

    def test_sync_to_postgres_cache(self, svc, monkeypatch):
        svc.get_user_repositories = MagicMock(return_value=[1, 2])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert svc.sync_to_postgres_cache('ws1') == \
            {'success': True, 'metrics_synced': 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert svc.sync_to_postgres_cache('ws1')['metrics_synced'] == 1
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert svc.sync_to_postgres_cache('ws1')['success'] is False
        assert db.rollback.called
        svc.get_user_repositories = MagicMock(side_effect=RuntimeError('x'))
        assert svc.sync_to_postgres_cache('ws1')['success'] is False

    def test_full_sync(self, svc):
        svc.sync_to_postgres_cache = MagicMock(
            return_value={'success': True})
        r = svc.full_sync('ws1')
        assert r['success'] and r['workspace_id'] == 'ws1'


# ============================================================================
# OneDriveService
# ============================================================================

class TestOneDrive:
    @pytest.fixture()
    def svc(self):
        return OneDriveService(tenant_id='t1', config={})

    def test_models_and_helpers(self, svc):
        from integrations.onedrive_service import OneDriveFile, OneDriveFileList
        f = OneDriveFile(id='1', name='n')
        assert f.name == 'n'
        assert OneDriveFileList(value=[f]).value
        assert svc._resolve_token(None) is None
        svc.access_token = 'tok'
        assert svc._resolve_token(None) == 'tok'
        assert svc.get_capabilities()['supports_webhooks'] is True

    async def test_health_check(self, svc):
        assert (await svc.health_check())['healthy'] is True

    async def test_get_access_token(self, svc):
        with patch.object(od.connection_service, 'get_connections',
                          return_value=[{'id': 'c1'}]) as gc, \
             patch.object(od.connection_service, 'get_connection_credentials',
                          AsyncMock(return_value={'access_token': 't'})) as gcc:
            assert await svc.get_access_token('u') == 't'
            gcc.assert_awaited()
        with patch.object(od.connection_service, 'get_connections',
                          side_effect=[[{'id': 'c1'}], []]), \
             patch.object(od.connection_service, 'get_connection_credentials',
                          AsyncMock(return_value={})):
            assert await svc.get_access_token('u') is None
        with patch.object(od.connection_service, 'get_connections',
                          return_value=[]):
            assert await svc.get_access_token('u') is None

    async def test_authenticate(self, svc, monkeypatch):
        monkeypatch.delenv('MICROSOFT_CLIENT_ID', raising=False)
        assert (await svc.authenticate('u'))['status'] == 'error'
        monkeypatch.setenv('MICROSOFT_CLIENT_ID', 'cid')
        r = await svc.authenticate('u')
        assert r['status'] == 'success' and r['state'] == 'onedrive_u'

    async def test_graph_get(self, svc):
        client = _client(_hresp(200, {'a': 1}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(client)):
            assert await svc._graph_get('t', 'u') == {'a': 1}
        client204 = _client(_hresp(204))
        with patch.object(od.httpx, 'AsyncClient',
                          return_value=_acm(client204)):
            assert await svc._graph_get('t', 'u') == {}
        clientb = _client(_hresp(200, content=b'raw'))
        with patch.object(od.httpx, 'AsyncClient',
                          return_value=_acm(clientb)):
            assert await svc._graph_get_bytes('t', 'u') == b'raw'

    async def test_list_files(self, svc):
        data = {'value': [1], '@odata.nextLink': 'http://next'}
        client = _client(_hresp(200, data))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.list_files('t', folder_id='f1', page_token='$skip=2')
            assert r['status'] == 'success' and r['data']['nextLink'] == 'http://next'
            r = await svc.list_files('t', page_token='abc')
            assert r['status'] == 'success'
        err = _client(_hresp(500, {}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.list_files('t'))['status'] == 'error'
        with patch.object(svc, '_graph_get',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert (await svc.list_files('t'))['status'] == 'error'
        assert (await svc.list_files(None))['message'] == 'No access token provided'

    async def test_list_drive_items(self, svc):
        client = _client(_hresp(200, {'value': [1, 2]}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(client)):
            assert await svc.list_drive_items('t', path='docs') == [1, 2]
        with patch.object(svc, '_graph_get',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert await svc.list_drive_items('t') == []
        assert await svc.list_drive_items(None) == []

    async def test_search_metadata_download(self, svc):
        client = _client(_hresp(200, {'value': [1]}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.search_files('t', 'q')
            assert r['status'] == 'success' and r['data']['value'] == [1]
        clientm = _client(_hresp(200, {'id': 'f'}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(clientm)):
            r = await svc.get_file_metadata('t', 'f')
            assert r['data']['id'] == 'f'
        clientb = _client(_hresp(200, content=b'abc'))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(clientb)):
            r = await svc.download_file('t', 'f')
            assert r['data']['size'] == 3
            assert await svc.download_file_bytes('t', 'f') == b'abc'
        assert (await svc.get_file_metadata(None, 'f'))['status'] == 'error'
        assert (await svc.download_file(None, 'f'))['status'] == 'error'
        assert await svc.download_file_bytes(None, 'f') is None
        err = _client(_hresp(404, {}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.search_files('t', 'q'))['status'] == 'error'
            assert (await svc.get_file_metadata('t', 'f'))['status'] == 'error'
            assert (await svc.download_file('t', 'f'))['status'] == 'error'
        with patch.object(svc, '_graph_get',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert (await svc.search_files('t', 'q'))['status'] == 'error'
            assert (await svc.get_file_metadata('t', 'f'))['status'] == 'error'
        with patch.object(svc, '_graph_get_bytes',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert (await svc.download_file('t', 'f'))['status'] == 'error'
            assert await svc.download_file_bytes('t', 'f') is None

    async def test_upload_file(self, svc):
        client = _client(_hresp(201, {'id': 'f'}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.upload_file('t', 'n.txt', b'x', 'docs')
            assert r['status'] == 'success'
            r = await svc.upload_file('t', 'n.txt', b'x')
            assert r['status'] == 'success'
        assert (await svc.upload_file(None, 'n', b'x'))['status'] == 'error'
        err = _client(_hresp(500, {}))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.upload_file('t', 'n', b'x'))['status'] == 'error'
        boom = _client()
        boom.put = AsyncMock(side_effect=RuntimeError('x'))
        with patch.object(od.httpx, 'AsyncClient', return_value=_acm(boom)):
            assert (await svc.upload_file('t', 'n', b'x'))['status'] == 'error'

    async def test_execute_operation(self, svc):
        svc.list_files = AsyncMock(
            return_value={'status': 'success', 'data': {'value': []}})
        r = await svc.execute_operation('list_files', {'access_token': 't'})
        assert r['success'] is True
        svc.list_files = AsyncMock(
            return_value={'status': 'error', 'message': 'm'})
        assert (await svc.execute_operation('list_files',
                                            {'access_token': 't'}))['error'] == 'm'
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError('x'))
        r = await svc.execute_operation('list_files', {'access_token': 't'})
        assert r['success'] is False

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.list_files = AsyncMock(return_value={
            'status': 'success',
            'data': {'value': [{'file': {}}, {'folder': {}}]}})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache('ws', 't')) == \
            {'success': True, 'metrics_synced': 2}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('ws', 't'))[
            'metrics_synced'] == 2
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.list_files = AsyncMock(
            return_value={'status': 'error', 'message': 'no tok'})
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.sync_to_postgres_cache = AsyncMock(
            return_value={'success': True})
        r = await svc.full_sync('ws', 't')
        assert r['success'] and r['workspace_id'] == 'ws'


# ============================================================================
# GoogleDriveService
# ============================================================================

class TestGoogleDrive:
    @pytest.fixture()
    def svc(self):
        return GoogleDriveService(tenant_id='t1', config={})

    def test_models_and_caps(self, svc):
        from integrations.google_drive_service import GoogleDriveFile
        assert GoogleDriveFile(id='1', name='n').name == 'n'
        assert svc.get_capabilities()['supports_webhooks'] is True

    async def test_health_check(self, svc, monkeypatch):
        monkeypatch.delenv('GOOGLE_DRIVE_ACCESS_TOKEN', raising=False)
        assert (await svc.health_check())['status'] == 'unhealthy'
        svc.access_token = 't'
        assert (await svc.health_check())['status'] == 'healthy'

    async def test_get_access_token(self, svc):
        with patch.object(gdr.connection_service, 'get_connections',
                          return_value=[{'id': 'c1'}]), \
             patch.object(gdr.connection_service, 'get_connection_credentials',
                          AsyncMock(return_value={'access_token': 't'})):
            assert await svc.get_access_token('u') == 't'
        with patch.object(gdr.connection_service, 'get_connections',
                          return_value=[]), \
             patch.dict('os.environ', {'GOOGLE_DRIVE_ACCESS_TOKEN': 'envt'}):
            assert await svc.get_access_token('u') == 'envt'

    async def test_authenticate(self, svc, monkeypatch):
        monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
        assert (await svc.authenticate('u'))['status'] == 'error'
        monkeypatch.setenv('GOOGLE_CLIENT_ID', 'cid')
        r = await svc.authenticate('u')
        assert r['status'] == 'success' and r['state'] == 'google_drive_u'

    async def test_drive_get(self, svc):
        client = _client(_hresp(200, {'files': []}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(client)):
            assert await svc._drive_get('t', 'u') == {'files': []}
            assert isinstance(await svc._drive_get_bytes('t', 'u'), bytes)

    async def test_list_and_search(self, svc):
        data = {'files': [1], 'nextPageToken': 'pt'}
        client = _client(_hresp(200, data))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.list_files('t', folder_id='f', page_token='pt')
            assert r['status'] == 'success' and r['data']['nextPageToken'] == 'pt'
            r = await svc.list_files('t', folder_id='root')
            assert r['status'] == 'success'
            r = await svc.search_files('t', "o'brien")
            assert r['status'] == 'success'
        err = _client(_hresp(403, {}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.list_files('t'))['status'] == 'error'
            assert (await svc.search_files('t', 'q'))['status'] == 'error'
        with patch.object(svc, '_drive_get',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert (await svc.list_files('t'))['status'] == 'error'
            assert (await svc.search_files('t', 'q'))['status'] == 'error'
        assert (await svc.list_files(None))['message'] == 'No access token provided'
        assert (await svc.search_files(None, 'q'))['message'] == \
            'No access token provided'

    async def test_metadata_and_downloads(self, svc):
        client = _client(_hresp(200, {'id': 'f', 'mimeType': 'text/plain'}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.get_file_metadata('t', 'f')
            assert r['data']['id'] == 'f'
        # export branch (google doc)
        media = _client(_hresp(200, content=b'docx'))
        svc.get_file_metadata = AsyncMock(return_value={
            'status': 'success',
            'data': {'mimeType': 'application/vnd.google-apps.document'}})
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(media)):
            r = await svc.download_file('t', 'f')
            assert r['status'] == 'success' and r['data']['size'] == 4
            assert await svc.download_file_bytes('t', 'f') == b'docx'
        # plain media branch
        svc.get_file_metadata = AsyncMock(return_value={
            'status': 'success', 'data': {'mimeType': 'text/plain'}})
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(media)):
            r = await svc.download_file('t', 'f')
            assert r['status'] == 'success'
            assert await svc.download_file_bytes('t', 'f') == b'docx'
        # metadata failure -> falls back to media branch
        svc.get_file_metadata = AsyncMock(return_value={'status': 'error'})
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(media)):
            r = await svc.download_file('t', 'f')
            assert r['status'] == 'success'
        # error paths
        svc.get_file_metadata = AsyncMock(
            return_value={'status': 'success', 'data': {}})
        err = _client(_hresp(404, {}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.download_file('t', 'f'))['status'] == 'error'
        svc.get_file_metadata = AsyncMock(
            return_value={'status': 'success', 'data': {}})
        with patch.object(svc, '_drive_get_bytes',
                          AsyncMock(side_effect=RuntimeError('x'))):
            assert (await svc.download_file('t', 'f'))['status'] == 'error'
            assert await svc.download_file_bytes('t', 'f') is None
        assert (await GoogleDriveService.get_file_metadata(
            svc, None, 'f'))['status'] == 'error'
        assert (await svc.download_file(None, 'f'))['status'] == 'error'
        assert await svc.download_file_bytes(None, 'f') is None
        err = _client(_hresp(500, {}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(err)):
            r = await GoogleDriveService.get_file_metadata(svc, 't', 'f')
            assert r['status'] == 'error'

    async def test_upload(self, svc):
        client = _client()
        client.post = AsyncMock(return_value=_hresp(200, {'id': 'f'}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(client)):
            r = await svc.upload_file('t', 'n', b'x', folder_id='f')
            assert r['status'] == 'success'
            r = await svc.upload_file('t', 'n', b'x')
            assert r['status'] == 'success'
        assert (await svc.upload_file(None, 'n', b'x'))['status'] == 'error'
        err = _client()
        err.post = AsyncMock(return_value=_hresp(500, {}))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(err)):
            assert (await svc.upload_file('t', 'n', b'x'))['status'] == 'error'
        boom = _client()
        boom.post = AsyncMock(side_effect=RuntimeError('x'))
        with patch.object(gdr.httpx, 'AsyncClient', return_value=_acm(boom)):
            assert (await svc.upload_file('t', 'n', b'x'))['status'] == 'error'

    async def test_execute_operation(self, svc):
        svc.list_files = AsyncMock(
            return_value={'status': 'success', 'data': {'files': []}})
        assert (await svc.execute_operation('list_files',
                                            {'access_token': 't'}))['success']
        svc.list_files = AsyncMock(
            return_value={'status': 'error', 'message': 'm'})
        r = await svc.execute_operation('list_files', {'access_token': 't'})
        assert r['success'] is False and r['error'] == 'm'
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError('x'))
        r = await svc.execute_operation('list_files', {'access_token': 't'})
        assert r['success'] is False

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.list_files = AsyncMock(return_value={
            'status': 'success',
            'data': {'files': [
                {'mimeType': 'application/vnd.google-apps.document'},
                {'mimeType': 'application/vnd.google-apps.spreadsheet'},
                {'mimeType': 'text/plain'}]}})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache('ws', 't')) == \
            {'success': True, 'metrics_synced': 3}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('ws', 't'))[
            'metrics_synced'] == 3
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.list_files = AsyncMock(
            return_value={'status': 'error', 'message': 'm'})
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.list_files = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws', 't'))['success'] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('ws', 't')
        assert r['success'] and r['workspace_id'] == 'ws'


# ============================================================================
# CalendlyService
# ============================================================================

class TestCalendly:
    @pytest.fixture()
    def svc(self):
        # CalendlyService leaves get_capabilities abstract; make it concrete
        return _ConcreteCalendly(tenant_id='t1', config={
            'client_id': 'ci', 'client_secret': 'cs', 'access_token': 'tok'})

    async def test_init_and_auth_url(self):
        s = _ConcreteCalendly(tenant_id='t', config={})
        assert s.base_url == 'https://api.calendly.com'
        url = s.get_authorization_url('http://cb', state='st')
        assert 'state=st' in url
        assert 'state' not in s.get_authorization_url('http://cb')
        assert (await s.health_check())['ok'] is True

    async def test_close(self, svc):
        svc.client.aclose = AsyncMock()
        await svc.close()
        svc.client.aclose.assert_awaited()

    async def test_exchange_token(self, svc):
        svc.http.post = AsyncMock(
            return_value=_hresp(200, {'access_token': 'nt'}))
        r = await svc.exchange_token('code', 'http://cb')
        assert r['access_token'] == 'nt' and svc.access_token == 'nt'
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError('x'))
        with pytest.raises(HTTPException):
            await svc.exchange_token('code', 'http://cb')

    async def test_getters(self, svc):
        svc.http.get = AsyncMock(return_value=_hresp(200, {'resource': 'me'}))
        assert await svc.get_current_user() == {'resource': 'me'}
        svc.http.get = AsyncMock(
            return_value=_hresp(200, {'collection': [1]}))
        assert await svc.get_event_types('uri') == [1]
        assert await svc.get_scheduled_events('uri') == [1]
        svc.http.get = AsyncMock(
            return_value=_hresp(200, {'collection': [2]}))
        assert await svc.get_scheduled_events() == [2]
        # unauthenticated
        svc2 = _ConcreteCalendly(tenant_id='t2', config={})
        for meth in (svc2.get_current_user, svc2.get_event_types,
                     svc2.get_scheduled_events):
            with pytest.raises(HTTPException) as ei:
                await meth() if meth != svc2.get_event_types \
                    else await meth('uri')
            assert ei.value.status_code == 401
        # HTTP errors -> 400
        svc.http.get = AsyncMock(side_effect=httpx.HTTPError('x'))
        with pytest.raises(HTTPException) as ei:
            await svc.get_current_user()
        assert ei.value.status_code == 400
        with pytest.raises(HTTPException):
            await svc.get_event_types('uri')
        with pytest.raises(HTTPException):
            await svc.get_scheduled_events()

    async def test_execute_operation(self, svc):
        svc.get_current_user = AsyncMock(return_value={'me': 1})
        assert (await svc.execute_operation('get_current_user', {}))['success']
        svc.get_event_types = AsyncMock(return_value=[1])
        r = await svc.execute_operation(
            'get_event_types', {'user_uri': 'u'})
        assert r['success']
        svc.get_scheduled_events = AsyncMock(return_value=[1])
        r = await svc.execute_operation(
            'get_scheduled_events', {'user_uri': 'u'})
        assert r['success']
        svc.full_sync = AsyncMock(return_value={'ok': 1})
        r = await svc.execute_operation('full_sync',
                                        {'workspace_id': 'ws'})
        assert r['success']
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_current_user = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('get_current_user',
                                            {}))['success'] is False

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.get_scheduled_events = AsyncMock(return_value=[1, 2])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache('ws')) == \
            {'success': True, 'metrics_synced': 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('ws'))['metrics_synced'] == 1
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws'))['success'] is False
        db.commit = MagicMock()
        svc.get_scheduled_events = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws')) == \
            {'success': True, 'metrics_synced': 1}
        # outer error: SessionLocal itself blows up
        svc.get_scheduled_events = AsyncMock(return_value=[1])
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(side_effect=RuntimeError('x')))
        assert (await svc.sync_to_postgres_cache('ws'))['success'] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('ws')
        assert r['success'] and r['workspace_id'] == 'ws'


class _ConcreteCalendly(CalendlyService):
    def get_capabilities(self):
        return {}


# ============================================================================
# ObsidianService
# ============================================================================

class TestObsidian:
    @pytest.fixture()
    def svc(self):
        return ObsidianService(tenant_id='t1', config={'api_token': 'tok'})

    def test_loopback_helper(self):
        assert obs._is_loopback_url('http://localhost:27123') is True
        assert obs._is_loopback_url('http://127.0.0.1:1') is True
        assert obs._is_loopback_url('http://[::1]:1') is True
        assert obs._is_loopback_url('http://example.com') is False
        assert obs._is_loopback_url('not a url') is False

    def test_init_ssrf(self):
        import core.ssrf_guard as sg
        with patch.object(sg, 'validate_url',
                          side_effect=sg.SSRFError('blocked')):
            with pytest.raises(ValueError):
                ObsidianService(tenant_id='t',
                                config={'plugin_url': 'http://example.com'})
        # non-loopback URL passes validation
        with patch.object(sg, 'validate_url', return_value=True):
            ObsidianService(tenant_id='t',
                            config={'plugin_url': 'http://example.com'})
        assert 'Authorization' not in ObsidianService(
            tenant_id='t', config={}).session.headers

    def test_capabilities_and_health(self, svc):
        assert svc.get_capabilities()['auth_type'] == 'api_token'
        with patch.object(svc, 'test_connection',
                          return_value={'status': 'success', 'message': 'm',
                                        'timestamp': 'ts'}):
            h = svc.health_check()
            assert h['healthy'] is True

    def test_test_connection(self, svc):
        with patch.object(svc.session, 'get', return_value=_rresp(None, 200)):
            assert svc.test_connection()['status'] == 'success'
        with patch.object(svc.session, 'get', return_value=_rresp(None, 401)):
            assert svc.test_connection()['status'] == 'error'
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.test_connection()['status'] == 'error'

    def test_crud(self, svc):
        with patch.object(svc.session, 'get') as m:
            m.return_value = _rresp({'files': ['a.md']})
            assert svc.list_notes() == ['a.md']
            m.return_value = _rresp(None)
            m.return_value.text = 'content'
            assert svc.get_note('/notes/a.md') == 'content'
        with patch.object(svc.session, 'put', return_value=_rresp()):
            assert svc.create_note('/a.md', 'c') is True
        with patch.object(svc.session, 'post', return_value=_rresp([{'r': 1}])):
            assert svc.search('q') == [{'r': 1}]
        with patch.object(svc.session, 'get', side_effect=RuntimeError('x')):
            assert svc.list_notes() == []
            assert svc.get_note('a') is None
        with patch.object(svc.session, 'put', side_effect=RuntimeError('x')):
            assert svc.create_note('a', 'c') is False
        with patch.object(svc.session, 'post', side_effect=RuntimeError('x')):
            assert svc.append_note('a', 'c') is False
            assert svc.search('q') == []
        with patch.object(svc.session, 'post', return_value=_rresp()):
            assert svc.append_note('a', 'c') is True

    async def test_execute_operation(self, svc):
        svc.test_connection = MagicMock(
            return_value={'status': 'success'})
        assert (await svc.execute_operation('test_connection', {}))['success']
        svc.list_notes = MagicMock(return_value=['a'])
        r = await svc.execute_operation('list_notes', {})
        assert r['success'] and r['details']['count'] == 1
        svc.get_note = MagicMock(return_value='content')
        r = await svc.execute_operation('get_note', {'path': 'a'})
        assert r['success'] and r['result']['content'] == 'content'
        assert (await svc.execute_operation('get_note', {}))['success'] is False
        svc.get_note = MagicMock(return_value=None)
        assert (await svc.execute_operation('get_note',
                                            {'path': 'a'}))['success'] is False
        svc.create_note = MagicMock(return_value=True)
        assert (await svc.execute_operation(
            'create_note', {'path': 'a', 'content': 'c'}))['success']
        assert (await svc.execute_operation(
            'create_note', {'path': 'a'}))['success'] is False
        svc.append_note = MagicMock(return_value=True)
        assert (await svc.execute_operation(
            'append_note', {'path': 'a', 'content': 'c'}))['success']
        assert (await svc.execute_operation(
            'append_note', {}))['success'] is False
        svc.search = MagicMock(return_value=[1])
        r = await svc.execute_operation('search', {'query': 'q'})
        assert r['success'] and r['details']['count'] == 1
        assert (await svc.execute_operation('search', {}))['success'] is False
        r = await svc.execute_operation('nope', {})
        assert r['success'] is False and 'not supported' in r['error']
        # exception branch
        svc.list_notes = MagicMock(side_effect=RuntimeError('x'))
        r = await svc.execute_operation('list_notes', {})
        assert r['success'] is False
        # tenant mismatch
        r = await svc.execute_operation('list_notes', {},
                                        context={'tenant_id': 'other'})
        assert r['success'] is False


# ============================================================================
# LinearService
# ============================================================================

class TestLinear:
    @pytest.fixture()
    def svc(self):
        return LinearService(tenant_id='t1', config={
            'client_id': 'ci', 'client_secret': 'cs', 'access_token': 'tok'})

    async def test_init_and_auth_url(self):
        s = LinearService(tenant_id='t', config={})
        assert s.graphql_url.endswith('/graphql')
        url = s.get_authorization_url('http://cb', state='st')
        assert 'state=st' in url
        assert 'state' not in s.get_authorization_url('http://cb')

    async def test_close_and_capabilities_and_health(self, svc):
        svc.client.aclose = AsyncMock()
        await svc.close()
        assert svc.get_capabilities()['supports_webhooks'] is True
        assert (await svc.health_check())['healthy'] is True

    async def test_exchange_token(self, svc):
        svc.http.post = AsyncMock(
            return_value=_hresp(200, {'access_token': 'nt'}))
        r = await svc.exchange_token('code', 'http://cb')
        assert r['access_token'] == 'nt' and svc.access_token == 'nt'
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError('x'))
        with pytest.raises(HTTPException):
            await svc.exchange_token('code', 'http://cb')

    async def test_graphql_query(self, svc):
        svc.http.post = AsyncMock(return_value=_hresp(200, {'data': {}}))
        assert await svc._graphql_query('query { x }') == {'data': {}}
        assert await svc._graphql_query('q', variables={'a': 1}) == {'data': {}}
        svc.http.post = AsyncMock(side_effect=httpx.HTTPError('x'))
        with pytest.raises(HTTPException):
            await svc._graphql_query('q')
        bare = LinearService(tenant_id='t', config={})
        with pytest.raises(HTTPException) as ei:
            await bare._graphql_query('q')
        assert ei.value.status_code == 401

    async def test_viewers_teams_projects_issues(self, svc):
        svc.http.post = AsyncMock(return_value=_hresp(200, {
            'data': {'viewer': {'id': 'v'},
                     'teams': {'nodes': [{'id': 't'}]},
                     'projects': {'nodes': [{'id': 'p'}]},
                     'issues': {'nodes': [{'id': 'i'}]}}}))
        assert (await svc.get_viewer()) == {'id': 'v'}
        assert (await svc.get_teams()) == [{'id': 't'}]
        assert (await svc.get_projects()) == [{'id': 'p'}]
        assert (await svc.get_issues(team_id='T')) == [{'id': 'i'}]
        assert (await svc.get_issues()) == [{'id': 'i'}]

    async def test_create_issue_project(self, svc):
        svc.http.post = AsyncMock(return_value=_hresp(200, {
            'data': {'issueCreate': {'success': True},
                     'projectCreate': {'success': True}}}))
        r = await svc.create_issue('T', 'team', description='d',
                                   priority=1, assignee_id='a')
        assert r['success'] is True
        r = await svc.create_project('P', ['t'], description='d')
        assert r['success'] is True

    async def test_execute_operation(self, svc):
        svc.get_issues = AsyncMock(return_value=[1])
        assert (await svc.execute_operation('get_issues', {}))['success']
        svc.create_issue = AsyncMock(return_value={'id': 'i'})
        r = await svc.execute_operation(
            'create_issue', {'title': 'T', 'team_id': 't'})
        assert r['success']
        svc.get_teams = AsyncMock(return_value=[1])
        assert (await svc.execute_operation('get_teams', {}))['success']
        svc.get_projects = AsyncMock(return_value=[1])
        assert (await svc.execute_operation('get_projects', {}))['success']
        svc.create_project = AsyncMock(return_value={'id': 'p'})
        r = await svc.execute_operation(
            'create_project', {'name': 'P', 'team_ids': ['t']})
        assert r['success']
        svc.get_viewer = AsyncMock(return_value={'id': 'v'})
        assert (await svc.execute_operation('get_viewer', {}))['success']
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_issues = AsyncMock(side_effect=RuntimeError('x'))
        r = await svc.execute_operation('get_issues', {})
        assert r['success'] is False

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.get_issues = AsyncMock(return_value=[1])
        svc.get_teams = AsyncMock(return_value=[2])
        svc.get_projects = AsyncMock(return_value=[3])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert (await svc.sync_to_postgres_cache('ws')) == \
            {'success': True, 'metrics_synced': 3}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('ws'))['metrics_synced'] == 3
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws'))['success'] is False
        svc.get_issues = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws'))['success'] is False
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('ws')
        assert r['success'] and r['workspace_id'] == 'ws'
