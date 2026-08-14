# -*- coding: utf-8 -*-
"""Coverage wave 87 — integrations.discord_enhanced_service,
integrations.hubspot_routes.

No network, no LLM: Discord HTTP/WebSocket boundaries are AsyncMock objects,
HubSpot httpx client is mocked, routes exercised through FastAPI TestClient
with dependency_overrides for get_current_user.
"""
import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

import integrations.discord_enhanced_service as de_mod
from integrations.discord_enhanced_service import (
    DiscordChannel,
    DiscordChannelType,
    DiscordConnectionStatus,
    DiscordEnhancedService,
    DiscordEventType,
    DiscordGuild,
    DiscordMessage,
    DiscordPermission,
    DiscordRateLimiter,
    DiscordUser,
)
import integrations.hubspot_routes as hr
from integrations.hubspot_routes import (
    HubSpotAuthRequest,
    HubSpotContactCreate,
    HubSpotDealCreate,
    HubSpotSearchRequest,
    HubSpotService,
)
from core.auth import get_current_user

FERNET_KEY = Fernet.generate_key().decode()


def http_response(payload=None, status=200, headers=None, text='body',
                  raise_exc=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json.return_value = payload if payload is not None else {}
    resp.headers = headers or {}
    if raise_exc is not None:
        resp.raise_for_status = MagicMock(side_effect=raise_exc)
    else:
        resp.raise_for_status = MagicMock()
    return resp


# ============================================================================
# Discord — models / post_init
# ============================================================================

def test_discord_guild_model():
    g = DiscordGuild(guild_id='G1', name='Guild', owner_id='O', owner_name='OW',
                     icon='ic')
    assert g.icon_url.endswith('/icons/G1/ic.png')
    assert g.roles == [] and g.integration_data == {}
    assert g.created_at is not None


def test_discord_channel_model():
    c = DiscordChannel(channel_id='C1', name='n', type=DiscordChannelType.VOICE,
                       guild_id='G', guild_name='N')
    assert c.is_voice and not c.is_text
    c2 = DiscordChannel(channel_id='C', name='n', type=DiscordChannelType.DM,
                        guild_id='G', guild_name='N')
    assert c2.is_private and not c2.is_thread
    c3 = DiscordChannel(channel_id='C', name='n', type=DiscordChannelType.STAGE,
                        guild_id='G', guild_name='N')
    assert c3.is_stage and c3.is_voice


def test_discord_message_model():
    m = DiscordMessage(message_id='M', content='c', channel_id='thread:C1',
                       guild_id='G', guild_name='N', user_id='U',
                       user_name='u', user_discriminator='0',
                       timestamp='t', edited_timestamp='e', type=19,
                       referenced_message={'message_id': 'R'},
                       webhook_id='W')
    assert m.thread_id == 'thread:C1'
    assert m.is_edited and m.is_crossposted and m.is_webhook
    assert m.reply_to_id == 'R'
    m2 = DiscordMessage(message_id='M', content='c', channel_id='C',
                        guild_id='G', guild_name='N', user_id='U', user_name='u',
                        user_discriminator='0', timestamp='t', type=24)
    assert m2.is_system and not m2.is_command and not m2.is_webhook


def test_discord_user_model():
    u = DiscordUser(user_id='U1', username='alice', discriminator='0001')
    assert u.display_name == 'alice' and u.roles == []
    u2 = DiscordUser(user_id='U1', username='a', discriminator='0',
                     avatar='av', guild_id='G')
    assert 'avatars/G/av' in u2.avatar_url


def test_discord_enums():
    assert DiscordEventType.READY.value == 'READY'
    assert DiscordConnectionStatus.RATE_LIMITED.value == 'rate_limited'
    assert DiscordPermission.ADMINISTRATOR.value == 0x8


# ============================================================================
# Discord — rate limiter
# ============================================================================

async def test_rate_limiter_local():
    rl = DiscordRateLimiter()
    for _ in range(5):
        assert await rl.check_limit('send_message', 'ch1') is True
    assert await rl.check_limit('send_message', 'ch1') is False
    # window expiry resets
    rl.local_limits['discord_rate:send_message:ch1']['reset'] = 0
    assert await rl.check_limit('send_message', 'ch1') is True


async def test_rate_limiter_redis():
    redis = MagicMock()
    redis.get.return_value = '99'
    rl = DiscordRateLimiter(redis)
    assert await rl.check_limit('send_message', 'ch') is False
    redis.get.return_value = '0'
    assert await rl.check_limit('send_message', 'ch') is True
    redis.pipeline.return_value.incr.assert_called()


async def test_rate_limiter_global_exhausted():
    rl = DiscordRateLimiter()
    rl.update_global_limit(0, 10)
    assert await rl.check_limit('send_message', 'x') is False


# ============================================================================
# Discord — service core
# ============================================================================

@pytest.fixture()
def svc():
    s = DiscordEnhancedService('t1', {
        'bot_token': 'tok', 'client_id': 'cid', 'client_secret': 'sec',
        'redirect_uri': 'http://r', 'encryption_key': FERNET_KEY})
    s.session = AsyncMock()
    return s


def test_service_init_defaults():
    s = DiscordEnhancedService('t', {})
    assert s.bot_token is None
    assert s.cipher is None
    assert s.rate_limiter is not None
    assert DiscordEventType.MESSAGE_CREATE in s.event_handlers


def test_capabilities_and_health(svc):
    caps = svc.get_capabilities()
    assert caps['supports_webhooks'] is True
    health = svc.health_check()
    assert health['ok'] is True and health['healthy'] is True
    svc.bot_token = None
    assert svc.health_check()['ok'] is False


def test_encrypt_decrypt(svc):
    token = 'secret-token'
    enc = svc._encrypt_token(token)
    assert svc._decrypt_token(enc) == token
    svc.cipher = None
    assert svc._encrypt_token(token) == token
    assert svc._decrypt_token(token) == token


def test_generate_oauth_url(svc):
    url = svc.generate_oauth_url('state1', 'u1')
    assert url.startswith('https://discord.com/oauth2/authorize')
    assert 'state=state1' in url and 'permissions=' in url
    url2 = svc.generate_oauth_url('s', 'u', scopes=['bot'])
    assert 'scope=bot' in url2


async def test_execute_operation(svc):
    svc.send_message = AsyncMock(return_value={'ok': True, 'message_id': 'M'})
    res = await svc.execute_operation('send_message', {
        'guild_id': 'G', 'channel_id': 'C', 'content': 'hi'})
    assert res['success'] is True
    res = await svc.execute_operation('bogus', {})
    assert res['success'] is False
    svc.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await svc.execute_operation('send_message', {}))['error']


async def test_get_service_info(svc):
    svc.connection_status['G1'] = DiscordConnectionStatus.CONNECTED
    svc.is_connected = True
    info = await svc.get_service_info()
    assert info['status']['connected_guilds'] == 1
    assert info['status']['websocket_connected'] is True
    assert 'send_message' in info['supported_operations']


# ============================================================================
# Discord — guild persistence (db + redis)
# ============================================================================

def _guild_row(**overrides):
    row = {
        'guild_id': 'G1', 'name': 'Guild', 'owner_id': 'O', 'owner_name': 'OW',
        'roles': '[]', 'emojis': '[]', 'features': '[]', 'scopes': '[]',
        'integration_data': '{}', 'welcome_screen': None,
        'stage_instances': '[]', 'stickers': '[]',
        'guild_scheduled_events': '[]', 'created_at': '2026-08-01T00:00:00+00:00',
    }
    row.update(overrides)
    return row


def test_get_guild_by_id_db(svc):
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = _guild_row()
    g = svc._get_guild_by_id('G1')
    assert g is not None and g.guild_id == 'G1'
    # db returns nothing -> None
    svc.db.execute.return_value.fetchone.return_value = None
    assert svc._get_guild_by_id('X') is None
    # db blows up -> None
    svc.db.execute.side_effect = RuntimeError('db')
    assert svc._get_guild_by_id('X') is None


def test_get_guild_by_id_redis_and_none(svc):
    svc.redis_client = MagicMock()
    svc.redis_client.get.return_value = json.dumps(_guild_row())
    assert svc._get_guild_by_id('G1').name == 'Guild'
    svc.redis_client.get.return_value = None
    svc2 = DiscordEnhancedService('t', {'bot_token': 'b'})
    svc2.db = None
    svc2.redis_client = None
    assert svc2._get_guild_by_id('G1') is None


def test_save_guild_db(svc):
    svc.db = MagicMock()
    guild = DiscordGuild(guild_id='G1', name='N', owner_id='O', owner_name='OW',
                         access_token='secret')
    assert svc._save_guild(guild) is True
    svc.db.commit.assert_called_once()
    assert svc.connection_status['G1'] == DiscordConnectionStatus.CONNECTED


def test_save_guild_redis_and_failure(svc):
    svc.redis_client = MagicMock()
    guild = DiscordGuild(guild_id='G2', name='N', owner_id='O', owner_name='OW')
    assert svc._save_guild(guild) is True
    svc.redis_client.setex.assert_called_once()
    # failure path
    svc.redis_client.setex.side_effect = RuntimeError('redis down')
    assert svc._save_guild(guild) is False


async def test_get_guilds_db(svc):
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchall.return_value = [
        _guild_row(guild_id='G1', user_id='U1'),
        _guild_row(guild_id='G2', user_id='U2')]
    guilds = await svc.get_guilds()
    assert len(guilds) == 2
    # with user filter (mock db returns same rows; filter is done in SQL)
    guilds = await svc.get_guilds(user_id='U1')
    assert len(guilds) == 2
    svc.db.execute.side_effect = RuntimeError('db')
    assert await svc.get_guilds() == []


async def test_get_guilds_redis(svc):
    svc.redis_client = MagicMock()
    svc.redis_client.keys.return_value = ['discord_guild:G1', 'discord_guild:G2']
    svc.redis_client.get.side_effect = [
        json.dumps(_guild_row(guild_id='G1', user_id='U1')),
        json.dumps(_guild_row(guild_id='G2', user_id='U2'))] * 2
    assert len(await svc.get_guilds()) == 2
    assert len(await svc.get_guilds(user_id='U2')) == 1


# ============================================================================
# Discord — OAuth code exchange
# ============================================================================

def _patch_async_client(monkeypatch, responses):
    """Patch httpx.AsyncClient used inside exchange_code_for_tokens."""
    client = MagicMock()
    for method, resp in responses.items():
        setattr(client, method, AsyncMock(return_value=resp))
    cls = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(return_value=client),
        __aexit__=AsyncMock(return_value=False)))
    monkeypatch.setattr(de_mod.httpx, 'AsyncClient', cls)
    return client


async def test_exchange_code_for_tokens_success(svc, monkeypatch):
    _patch_async_client(monkeypatch, {
        'post': http_response({'access_token': 'AT', 'refresh_token': 'RT',
                               'scope': 'bot identify'}),
        'get': http_response({'id': 'U1', 'username': 'alice'})})
    svc._save_guild = MagicMock(return_value=True)
    # guilds fetch returns 200 with one guild
    client = svc  # placeholder to keep symmetry
    with patch.object(type(svc), '_save_guild', MagicMock(return_value=True)):
        svc.db = None
        svc.redis_client = None
        # second get call is guilds list
        resp_calls = {
            'post': http_response({'access_token': 'AT', 'refresh_token': 'RT',
                                   'scope': 'bot identify'}),
        }
        _patch_async_client(monkeypatch, resp_calls)
        # users/@me then guilds
        import integrations.discord_enhanced_service as m
        user_resp = http_response({'id': 'U1', 'username': 'alice'})
        guild_resp = http_response([
            {'id': 'G1', 'name': 'Guild', 'features': ['F'],
             'approximate_member_count': 5, 'owner_id': 'U1'}])
        patched = m.httpx.AsyncClient.return_value.__aenter__.return_value
        patched.get = AsyncMock(side_effect=[user_resp, guild_resp])
        svc._save_guild = MagicMock(return_value=True)
        result = await svc.exchange_code_for_tokens('code', 'state')
    assert result['ok'] is True
    assert result['access_token'] == 'AT'
    assert len(result['guilds']) == 1
    assert svc._save_guild.called


async def test_exchange_code_for_tokens_errors(svc, monkeypatch):
    # token endpoint non-200
    _patch_async_client(monkeypatch, {
        'post': http_response({}, status=400, text='bad')})
    res = await svc.exchange_code_for_tokens('c', 's')
    assert res['ok'] is False
    # generic exception
    _patch_async_client(monkeypatch, {
        'post': AsyncMock(side_effect=RuntimeError('net')).return_value})
    cls_resp = de_mod.httpx.AsyncClient.return_value
    cls_resp.__aenter__.return_value.post = AsyncMock(
        side_effect=RuntimeError('net'))
    res = await svc.exchange_code_for_tokens('c', 's')
    assert res['ok'] is False and 'net' in res['error']


# ============================================================================
# Discord — test_connection
# ============================================================================

async def test_test_connection_success(svc):
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = _guild_row()
    svc.session.get = AsyncMock(return_value=http_response(
        {'approximate_member_count': 42}))
    res = await svc.test_connection('G1')
    assert res['connected'] is True and res['status'] == 'connected'
    assert svc.connection_status['G1'] == DiscordConnectionStatus.CONNECTED


async def test_test_connection_failures(svc):
    # guild missing
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = None
    res = await svc.test_connection('X')
    assert res['connected'] is False and res['status'] == 'error'
    # session missing
    svc.db.execute.return_value.fetchone.return_value = _guild_row()
    svc.session = None
    res = await svc.test_connection('G1')
    assert 'session not available' in res['error'].lower()
    # API non-200
    svc.session = AsyncMock()
    svc.session.get = AsyncMock(return_value=http_response({}, status=403))
    res = await svc.test_connection('G1')
    assert res['connected'] is False


# ============================================================================
# Discord — send_message / get_channel_messages / search
# ============================================================================

async def test_send_message_success(svc):
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.session.post = AsyncMock(return_value=http_response(
        {'id': 'M1', 'channel_id': 'C1', 'guild_id': 'G1',
         'timestamp': 't', 'content': 'hi'},
        headers={'X-RateLimit-Remaining': '40',
                 'X-RateLimit-Reset-After': '2'}))
    res = await svc.send_message('G1', 'C1', 'hello', embed={'e': 1},
                                 components=[{'c': 1}], tts=True)
    assert res['ok'] is True and res['message_id'] == 'M1'


async def test_send_message_failures(svc):
    svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    res = await svc.send_message('G', 'C', 'x')
    assert res['ok'] is False and 'Rate limit' in res['error']
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.session = None
    res = await svc.send_message('G', 'C', 'x')
    assert res['ok'] is False
    svc.session = AsyncMock()
    svc.session.post = AsyncMock(return_value=http_response({}, status=403))
    assert (await svc.send_message('G', 'C', 'x'))['ok'] is False


MSG_PAYLOAD = {
    'id': 'M1', 'channel_id': 'C1', 'content': 'hello',
    'timestamp': '2026-08-10T01:00:00Z',
    'author': {'id': 'U1', 'username': 'alice', 'discriminator': '0001',
               'global_name': 'Alice'},
    'member': {'nick': 'Al'},
    'mentions': [], 'attachments': [], 'embeds': [], 'reactions': [],
    'type': 0, 'webhook_id': None,
}


async def test_get_channel_messages_success(svc):
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = None
    svc.redis_client = MagicMock()
    svc.session.get = AsyncMock(return_value=http_response([MSG_PAYLOAD]))
    msgs = await svc.get_channel_messages('G1', 'C1', limit=200,
                                          before='b', after='a', around='r')
    assert len(msgs) == 1
    assert msgs[0].user_display_name == 'Al'
    assert msgs[0].guild_name == 'Unknown Server'
    svc.redis_client.setex.assert_called_once()


async def test_get_channel_messages_errors(svc):
    svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert await svc.get_channel_messages('G', 'C') == []
    # API error, no cache
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.session.get = AsyncMock(return_value=http_response({}, status=500))
    svc.redis_client = None
    assert await svc.get_channel_messages('G', 'C') == []
    # API error with cache -> cached messages returned
    svc.redis_client = MagicMock()
    cached = {'message_id': 'M2', 'content': 'cached', 'channel_id': 'C1',
              'guild_id': 'G', 'guild_name': 'N', 'user_id': 'U',
              'user_name': 'u', 'user_discriminator': '0', 'timestamp': 't'}
    svc.redis_client.get.return_value = json.dumps([cached])
    msgs = await svc.get_channel_messages('G', 'C')
    assert len(msgs) == 1 and msgs[0].message_id == 'M2'


async def test_search_messages(svc):
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.session.post = AsyncMock(return_value=http_response(
        {'messages': [{'results': []}], 'total_results': 1}))
    res = await svc.search_messages('G', 'C', 'hello', before='b', after='a')
    assert res['ok'] is True and res['total'] == 1
    # failures
    svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await svc.search_messages('G', 'C', 'q'))['ok'] is False
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc.session.post = AsyncMock(return_value=http_response({}, status=500))
    assert (await svc.search_messages('G', 'C', 'q'))['ok'] is False


# ============================================================================
# Discord — postgres sync / full sync / close
# ============================================================================

async def test_sync_to_postgres_cache(svc, monkeypatch):
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = _guild_row(
        member_count=10, channel_count=3,
        integration_data='{"total_messages": 7}')
    session = MagicMock()
    session.query.return_value.filter_by.return_value.first.return_value = None
    core_db = SimpleNamespace(SessionLocal=MagicMock(return_value=session),
                              IntegrationMetric=MagicMock())
    import sys
    fake_core = MagicMock()
    fake_core.SessionLocal = MagicMock(return_value=session)
    monkeypatch.setitem(sys.modules, 'core.database', fake_core)
    monkeypatch.setitem(sys.modules, 'core.models', fake_core)
    with patch.dict('sys.modules', {'core.database': fake_core,
                                    'core.models': fake_core}):
        res = await svc.sync_to_postgres_cache('G1')
    assert res['success'] is True and res['metrics_synced'] == 3
    # guild missing
    svc.db.execute.return_value.fetchone.return_value = None
    res = await svc.sync_to_postgres_cache('X')
    assert res['success'] is False
    # commit failure
    svc.db.execute.return_value.fetchone.return_value = _guild_row()
    session.commit = MagicMock(side_effect=RuntimeError('pg'))
    res = await svc.sync_to_postgres_cache('G1')
    assert res['success'] is False
    session.rollback.assert_called()
    session.close.assert_called()


async def test_full_sync(svc):
    svc.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 3})
    res = await svc.full_sync('G1')
    assert res['success'] is True and res['postgres_cache']['metrics_synced'] == 3


async def test_close(svc):
    svc.websocket = MagicMock()
    svc.websocket.close = AsyncMock()
    svc.session.aclose = AsyncMock()
    await svc.close()
    svc.websocket.close.assert_awaited_once()
    svc.session.aclose.assert_awaited_once()


def test_setup_session_failure(monkeypatch):
    with patch.object(de_mod.httpx, 'AsyncClient',
                      MagicMock(side_effect=RuntimeError('no session'))):
        s = DiscordEnhancedService.__new__(DiscordEnhancedService)
        s.bot_token = 't'
        s.session = 'sentinel'
        s._setup_session()
        assert s.session is None


# ============================================================================
# HubSpot — service methods (httpx client mocked)
# ============================================================================

@pytest.fixture()
def hs(monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    svc = HubSpotService()
    svc.client = AsyncMock()
    return svc


async def test_hs_authenticate_success(hs):
    hs.client.post = AsyncMock(return_value=http_response(
        {'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 1800}))
    hs.client.get = AsyncMock(return_value=http_response({'portalId': 123}))
    res = await hs.authenticate(HubSpotAuthRequest(
        client_id='cid', client_secret='cs',
        redirect_uri='http://r', code='c'))
    assert res['access_token'] == 'AT' and res['hub_id'] == 123


async def test_hs_authenticate_errors(hs):
    hs.client.post = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.authenticate(HubSpotAuthRequest(
            client_id='c', client_secret='c', redirect_uri='r', code='c'))
    hs.client.post = AsyncMock(side_effect=RuntimeError('net'))
    with pytest.raises(Exception):
        await hs.authenticate(HubSpotAuthRequest(
            client_id='c', client_secret='c', redirect_uri='r', code='c'))
    # _get_hub_id failure swallowed
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(side_effect=RuntimeError('net'))
    await hs._get_hub_id()
    assert hs.hub_id is None


def _unauthorized(hs):
    hs.access_token = None
    return hs


async def test_hs_get_contacts(hs):
    _unauthorized(hs)
    with pytest.raises(Exception) as e:
        await hs.get_contacts()
    assert '401' in str(e.value.status_code)
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(return_value=http_response({
        'results': [{'id': '1', 'properties': {
            'email': 'a@x.com', 'firstname': 'A', 'createdate': '1000',
            'lastmodifieddate': '2000', 'lifecyclestage': 'lead'}}]}))
    contacts = await hs.get_contacts(limit=10, offset=5)
    assert len(contacts) == 1 and contacts[0].email == 'a@x.com'
    # http error
    hs.client.get = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.get_contacts()
    # generic error
    hs.client.get = AsyncMock(side_effect=RuntimeError('net'))
    with pytest.raises(Exception):
        await hs.get_contacts()
    # wrapper unauthenticated
    hs.access_token = None
    with pytest.raises(Exception):
        await hs.get_contacts_wrapper()


async def test_hs_get_companies(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.get_companies()
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(return_value=http_response({
        'results': [{'id': '1', 'properties': {
            'name': 'Acme', 'createdate': '1000',
            'lastmodifieddate': '2000'}}]}))
    companies = await hs.get_companies(offset=2)
    assert companies[0].name == 'Acme'
    hs.client.get = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.get_companies()
    hs.client.get = AsyncMock(side_effect=RuntimeError('net'))
    with pytest.raises(Exception):
        await hs.get_companies()


async def test_hs_get_deals(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.get_deals()
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(return_value=http_response({
        'results': [{'id': '1', 'properties': {
            'dealname': 'D', 'amount': '500', 'dealstage': 's',
            'pipeline': 'p', 'closedate': '3000', 'createdate': '1000',
            'lastmodifieddate': '2000', 'hubspot_owner_id': 'O'}}]}))
    deals = await hs.get_deals(offset=1)
    assert deals[0].deal_name == 'D' and deals[0].amount == 500.0
    assert deals[0].close_date is not None
    hs.client.get = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.get_deals()
    hs.client.get = AsyncMock(side_effect=RuntimeError('net'))
    with pytest.raises(Exception):
        await hs.get_deals()
    hs.access_token = None
    with pytest.raises(Exception):
        await hs.get_deals_wrapper()


async def test_hs_get_campaigns(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.get_campaigns()
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(return_value=http_response({
        'campaigns': [{'id': 'c1', 'name': 'C', 'type': 'email',
                       'status': 'active', 'createdAt': '1000',
                       'updatedAt': '2000', 'numIncluded': 5,
                       'numResponded': 2}]}))
    campaigns = await hs.get_campaigns(offset=3)
    assert campaigns[0].num_included == 5
    hs.client.get = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.get_campaigns()
    hs.client.get = AsyncMock(side_effect=RuntimeError('boom'))
    with pytest.raises(Exception):
        await hs.get_campaigns()


async def test_hs_get_lists(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.get_lists()
    hs.access_token = 'AT'
    hs.client.get = AsyncMock(return_value=http_response({
        'lists': [{'listId': '1', 'name': 'L', 'listType': 'static',
                   'createdAt': '1000', 'lastProcessingFinishedAt': '2000',
                   'metaData': {'size': 9}}]}))
    lists = await hs.get_lists(offset=4)
    assert lists[0].member_count == 9
    hs.client.get = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.get_lists()
    hs.client.get = AsyncMock(side_effect=RuntimeError('x'))
    with pytest.raises(Exception):
        await hs.get_lists()


async def test_hs_search_content(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.search_content(HubSpotSearchRequest(query='q'))
    hs.access_token = 'AT'
    hs.client.post = AsyncMock(return_value=http_response(
        {'results': [{'id': '1'}], 'total': 1}))
    res = await hs.search_content(HubSpotSearchRequest(query='q'))
    assert res.total == 1
    hs.client.post = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.search_content(HubSpotSearchRequest(query='q'))
    hs.client.post = AsyncMock(side_effect=RuntimeError('x'))
    with pytest.raises(Exception):
        await hs.search_content(HubSpotSearchRequest(query='q'))


async def test_hs_create_contact(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.create_contact(HubSpotContactCreate(email='a@x.com'))
    hs.access_token = 'AT'
    hs.client.post = AsyncMock(return_value=http_response({'id': '1'}))
    res = await hs.create_contact(HubSpotContactCreate(
        email='a@x.com', first_name='A'))
    assert res['id'] == '1'
    hs.client.post = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.create_contact(HubSpotContactCreate(email='a'))
    hs.client.post = AsyncMock(side_effect=RuntimeError('x'))
    with pytest.raises(Exception):
        await hs.create_contact(HubSpotContactCreate(email='a'))


async def test_hs_create_deal(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.create_deal(HubSpotDealCreate(
            deal_name='D', stage='s', pipeline='p'))
    hs.access_token = 'AT'
    hs.client.post = AsyncMock(return_value=http_response({'id': 'D1'}))
    res = await hs.create_deal(HubSpotDealCreate(
        deal_name='D', amount=100.0, stage='s', pipeline='p',
        close_date=datetime(2026, 8, 10, tzinfo=timezone.utc)))
    assert res['id'] == 'D1'
    hs.client.post = AsyncMock(return_value=http_response(
        {}, raise_exc=__import__('httpx').HTTPError('x')))
    with pytest.raises(Exception):
        await hs.create_deal(HubSpotDealCreate(deal_name='D', stage='s',
                                               pipeline='p'))
    hs.client.post = AsyncMock(side_effect=RuntimeError('x'))
    with pytest.raises(Exception):
        await hs.create_deal(HubSpotDealCreate(deal_name='D', stage='s',
                                               pipeline='p'))


async def test_hs_get_stats(hs):
    _unauthorized(hs)
    with pytest.raises(Exception):
        await hs.get_stats()
    hs.access_token = 'AT'
    hs.advanced_service = None
    stats = await hs.get_stats()
    assert stats.total_contacts == 1500
    hs.advanced_service = SimpleNamespace(
        analytics_metrics={'total_contacts': 3, 'total_revenue': 9.5})
    stats = await hs.get_stats()
    assert stats.total_contacts == 3 and stats.total_revenue == 9.5


async def test_hs_health_checks(hs, monkeypatch):
    res = await hs.health_check()
    assert res['ok'] is True and res['service'] == 'hubspot'
    # wrapper mock mode
    mock_mgr = MagicMock()
    mock_mgr.is_mock_mode.return_value = True
    monkeypatch.setattr(hr, 'get_mock_mode_manager', lambda: mock_mgr)
    res = await hs.health_check_wrapper()
    assert res.get('is_mock') is True
    mock_mgr.is_mock_mode.return_value = False
    res = await hs.health_check_wrapper()
    assert res['status'] == 'healthy' and 'is_mock' not in res


# ============================================================================
# HubSpot — routes via TestClient
# ============================================================================

@pytest.fixture()
def client(monkeypatch):
    app = FastAPI()
    app.include_router(hr.router)
    app.dependency_overrides[get_current_user] = \
        lambda: SimpleNamespace(id='u1', tenant_id='t1')
    return TestClient(app)


def _fake_service_factory(monkeypatch, service):
    monkeypatch.setattr(hr, 'HubSpotService', lambda: service)


def test_route_auth_start_missing_client_id(client, monkeypatch):
    monkeypatch.delenv('HUBSPOT_CLIENT_ID', raising=False)
    res = client.get('/api/hubspot/auth/start')
    assert res.status_code == 200
    assert res.json()['ok'] is False


def test_route_auth_start_ok(client, monkeypatch):
    monkeypatch.setenv('HUBSPOT_CLIENT_ID', 'cid123')
    res = client.get('/api/hubspot/auth/start')
    body = res.json()
    assert body['ok'] is True
    assert body['auth_url'].startswith('https://app.hubspot.com/oauth/authorize')


def test_route_callback(client, monkeypatch):
    svc = MagicMock()
    svc.authenticate = AsyncMock(return_value={'access_token': 'AT'})
    _fake_service_factory(monkeypatch, svc)
    res = client.post('/api/hubspot/callback', json={
        'client_id': 'c', 'client_secret': 's',
        'redirect_uri': 'http://r', 'code': 'x'})
    assert res.status_code == 200 and res.json()['access_token'] == 'AT'


def test_route_crud_endpoints(client, monkeypatch):
    contact = hr.HubSpotContact(
        id='1', email='a@x.com', created_at=datetime(2026, 8, 1),
        last_modified=datetime(2026, 8, 2))
    svc = MagicMock()
    svc.get_contacts_wrapper = AsyncMock(return_value=[contact])
    svc.get_companies = AsyncMock(return_value=[hr.HubSpotCompany(
        id='1', name='Acme', created_at=datetime(2026, 8, 1),
        last_modified=datetime(2026, 8, 2))])
    deal = hr.HubSpotDeal(
        id='1', deal_name='D', stage='s', pipeline='p',
        created_at=datetime(2026, 8, 1), last_modified=datetime(2026, 8, 2))
    svc.get_deals_wrapper = AsyncMock(return_value=[deal])
    svc.get_campaigns = AsyncMock(return_value=[hr.HubSpotCampaign(
        id='1', name='C', type='t', status='a',
        created_at=datetime(2026, 8, 1), last_modified=datetime(2026, 8, 2),
        num_included=1, num_responded=0)])
    svc.get_lists = AsyncMock(return_value=[hr.HubSpotList(
        id='1', name='L', list_type='static',
        created_at=datetime(2026, 8, 1), member_count=2)])
    svc.search_content = AsyncMock(return_value=hr.HubSpotSearchResponse(
        results=[{'id': '1'}], total=1))
    svc.create_contact = AsyncMock(return_value={'id': 'C1'})
    svc.create_deal = AsyncMock(return_value={'id': 'D1'})
    svc.get_stats = AsyncMock(return_value=hr.HubSpotStats(
        total_contacts=1, total_companies=1, total_deals=1,
        total_campaigns=1, active_deals=1, won_deals=0, lost_deals=0,
        total_revenue=0.0))
    svc.health_check_wrapper = AsyncMock(return_value={
        'ok': True, 'status': 'healthy', 'service': 'hubspot',
        'timestamp': 't', 'version': '1.0.0'})
    _fake_service_factory(monkeypatch, svc)

    assert client.get('/api/hubspot/contacts?limit=5&offset=1').json()[0]['id'] == '1'
    assert client.get('/api/hubspot/companies').status_code == 200
    assert client.get('/api/hubspot/deals').json()[0]['deal_name'] == 'D'
    assert client.get('/api/hubspot/campaigns?offset=2').status_code == 200
    assert client.get('/api/hubspot/lists?offset=2').json()[0]['name'] == 'L'
    assert client.post('/api/hubspot/search',
                       json={'query': 'q'}).json()['total'] == 1
    assert client.post('/api/hubspot/contacts/create',
                       json={'email': 'a@x.com'}).json()['id'] == 'C1'
    assert client.post('/api/hubspot/deals/create', json={
        'deal_name': 'D', 'stage': 's', 'pipeline': 'p'}).json()['id'] == 'D1'
    assert client.get('/api/hubspot/stats').json()['total_contacts'] == 1
    assert client.get('/api/hubspot/health').json()['ok'] is True
    assert client.get('/api/hubspot/').json()['service'] == 'hubspot'


def test_route_analytics_advanced(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = SimpleNamespace(analytics_metrics={
        'total_contacts': 5, 'total_companies': 2, 'total_deals': 3,
        'total_revenue': 100.0, 'win_rate': 50.0, 'monthly_revenue': 10.0,
        'top_campaigns': [{'name': 'C', 'performance': 90, 'roi': 2,
                           'budget': 5}],
        'recent_activities': [{'type': 'Deal', 'description': 'd',
                               'timestamp': 't', 'contact': 'c'}],
        'pipeline_stages': [{'stage': 'S1', 'count': 2, 'value': 3.0,
                             'probability': 10.0}],
    })
    _fake_service_factory(monkeypatch, svc)
    body = client.get('/api/hubspot/analytics').json()
    assert body['totalContacts'] == 5
    assert body['topPerformingCampaigns'][0]['name'] == 'C'
    assert body['pipelineStages'][0]['stage'] == 'S1'
    assert body['recentActivities'][0]['type'] == 'Deal'


def test_route_analytics_fallback(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = None
    _fake_service_factory(monkeypatch, svc)
    body = client.get('/api/hubspot/analytics').json()
    assert body['totalContacts'] == 1547
    assert len(body['topPerformingCampaigns']) == 3


def test_route_analytics_empty_metrics_defaults(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = SimpleNamespace(analytics_metrics={})
    _fake_service_factory(monkeypatch, svc)
    body = client.get('/api/hubspot/analytics').json()
    assert body['totalContacts'] == 1547
    assert body['topPerformingCampaigns'][0]['name'] == 'Product Launch Q4'


def test_route_ai_predictions(client):
    body = client.get('/api/hubspot/ai/predictions').json()
    assert len(body['models']) == 3
    assert len(body['predictions']) == 2
    assert len(body['forecast']) == 4
    assert body['forecast'][2]['actual'] is None


def test_route_analyze_lead_advanced(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = SimpleNamespace(
        _score_lead=AsyncMock(return_value=85))
    _fake_service_factory(monkeypatch, svc)
    body = client.post('/api/hubspot/ai/analyze-lead',
                       json={'contact_id': 'c1'}).json()
    assert body['leadScore'] == 85.0
    assert body['timeframe'] == '2-4 weeks'
    assert body['recommendations'][0]['action'] == 'High Priority Follow-up'


def test_route_analyze_lead_advanced_exception(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = SimpleNamespace(
        _score_lead=AsyncMock(side_effect=RuntimeError('ai down')))
    _fake_service_factory(monkeypatch, svc)
    body = client.post('/api/hubspot/ai/analyze-lead',
                       json={'contact_id': 'c1'}).json()
    assert 60 <= body['leadScore'] <= 95
    assert len(body['keyFactors']) == 2


def test_route_analyze_lead_fallback(client, monkeypatch):
    svc = MagicMock()
    svc.advanced_service = None
    _fake_service_factory(monkeypatch, svc)
    body = client.post('/api/hubspot/ai/analyze-lead',
                       json={'contact_id': 'c1'}).json()
    assert 60 <= body['leadScore'] <= 95


def test_route_requires_auth(monkeypatch):
    app = FastAPI()
    app.include_router(hr.router)
    # no dependency override -> auth dependency is real get_current_user
    with TestClient(app) as c:
        res = c.get('/api/hubspot/contacts')
        assert res.status_code in (401, 403)
