# -*- coding: utf-8 -*-
"""Coverage wave 87 — integrations.whatsapp_business_integration,
integrations.hubspot_service, integrations.whatsapp_fastapi_routes.

No network: requests/httpx boundaries, psycopg2 connections and the
universal webhook bridge are all mocked.
"""
import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import integrations.whatsapp_business_integration as wa_mod
from integrations.whatsapp_business_integration import (
    WhatsAppBusinessIntegration,
    _process_incoming_message,
    initialize_whatsapp_integration,
    webhook as flask_webhook,
    health_check as flask_health,
    send_message_route as flask_send,
    get_conversations as flask_conversations,
    get_messages as flask_messages,
    create_template as flask_create_template,
    get_analytics as flask_analytics,
)
import integrations.hubspot_service as hs_mod
from integrations.hubspot_service import HubSpotService, get_hubspot_service
import integrations.whatsapp_fastapi_routes as wfr
from core.auth import get_current_user


def _resp(status=200, payload=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.headers = headers or {}
    r.raise_for_status.return_value = None
    return r


# ============================================================================
# WhatsAppBusinessIntegration — core
# ============================================================================

WA_CFG = {'access_token': 'tok', 'phone_number_id': 'pid',
          'webhook_verify_token': 'vtok', 'app_secret': 'secret'}


@pytest.fixture()
def wa():
    return WhatsAppBusinessIntegration(tenant_id='t1', config=dict(WA_CFG))


def test_wa_capabilities_health(wa):
    caps = wa.get_capabilities()
    assert caps['supports_webhooks'] is True
    assert wa.health_check()['healthy'] is True
    unconf = WhatsAppBusinessIntegration()
    assert unconf.health_check()['healthy'] is False


def test_wa_initialize_demo_mode(wa):
    with patch.object(wa_mod.psycopg2, 'connect',
                      side_effect=RuntimeError('no db')):
        assert wa.initialize({'is_demo': True, 'access_token': 'a'}) is True
        assert wa.db_connection is None
        # non-demo failure
        assert wa.initialize({}) is False


def test_wa_initialize_success_and_outer_error(wa):
    conn = MagicMock()
    with patch.object(wa_mod.psycopg2, 'connect', return_value=conn):
        assert wa.initialize({}) is True
    assert wa.db_connection is conn
    with patch.object(wa_mod, 'psycopg2',
                      MagicMock(**{'connect.side_effect': RuntimeError('x')})):
        # db failure in non-demo mode -> False
        assert wa.initialize({'database': {'host': 'h'}}) is False


def test_wa_create_tables(wa):
    wa.db_connection = None
    wa._create_tables()  # no connection branch
    conn = MagicMock()
    wa.db_connection = conn
    wa._create_tables()
    assert conn.cursor.return_value.__enter__.return_value.execute.call_count == 4
    conn.commit.assert_called_once()
    # failure branch
    conn.cursor.return_value.__enter__.return_value.execute.side_effect = \
        RuntimeError('sql err')
    with pytest.raises(RuntimeError):
        wa._create_tables()
    conn.rollback.assert_called()


async def test_wa_get_credential_branches(wa):
    assert (await wa._get_credentials())['access_token'] == 'tok'
    unconf = WhatsAppBusinessIntegration()
    with pytest.raises(wa_mod.AuthenticationError):
        await unconf._get_credentials()
    with patch.object(wa_mod, 'connection_service') as cs:
        cs.get_connections.return_value = []
        with pytest.raises(wa_mod.AuthenticationError):
            await unconf._get_credentials('u1')
        cs.get_connections.return_value = [{'id': 'c1'}]
        cs.get_connection_credentials = AsyncMock(return_value={'x': 1})
        with pytest.raises(wa_mod.AuthenticationError):
            await unconf._get_credentials('u1')
        cs.get_connection_credentials = AsyncMock(
            return_value={'access_token': 'a', 'phone_number_id': 'p'})
        creds = await unconf._get_credentials('u1')
        assert creds['access_token'] == 'a'


def _ok_send_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {'messages': [{'id': 'mid1'}]}
    return r


async def test_wa_send_message_types(wa):
    wa._store_message = MagicMock()
    with patch.object(wa_mod.requests, 'post',
                      return_value=_ok_send_response()) as post:
        res = await wa.send_message('123', 'text', {'body': 'hi'})
        assert res == {'success': True, 'message_id': 'mid1', 'status': 'sent'}
        res = await wa.send_message('123', 'template', {'name': 't'})
        res = await wa.send_message('123', 'media',
                                    {'media_type': 'image', 'link': 'l'})
        res = await wa.send_message('123', 'media', {'link': 'l'})  # default
        res = await wa.send_message('123', 'interactive', {'x': 1})
        assert res['success'] is True
        assert post.call_count == 5
    wa._store_message.assert_called()
    # unsupported type
    res = await wa.send_message('123', 'bogus', {})
    assert res['success'] is False and res['error'] == 'Failed to send WhatsApp message'


async def test_wa_send_message_failures(wa):
    bad = MagicMock()
    bad.status_code = 400
    bad.json.return_value = {'error': 'oops'}
    with patch.object(wa_mod.requests, 'post', return_value=bad):
        res = await wa.send_message('123', 'text', {})
        assert res == {'success': False, 'error': {'error': 'oops'}}
    # missing phone_number_id
    svc = WhatsAppBusinessIntegration(config={'access_token': 'a'})
    assert (await svc.send_message('1', 'text', {}))['success'] is False
    # credential error
    svc2 = WhatsAppBusinessIntegration(config={'phone_number_id': 'p'})
    with patch.object(svc2, '_get_credentials',
                      AsyncMock(side_effect=RuntimeError('x'))):
        assert (await svc2.send_message('1', 'text', {}))['success'] is False


async def test_wa_execute_operation(wa):
    wa.send_message = AsyncMock(return_value={'success': True})
    res = await wa.execute_operation('send_message', {
        'to': '1', 'type': 'text', 'content': {}}, context={'user_id': 'u'})
    assert res['success'] is True
    with pytest.raises(NotImplementedError):
        await wa.execute_operation('bogus', {})


def _db_conn(fetchall=None, fetchone=None):
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = fetchall or []
    cur.fetchone.return_value = fetchone
    return conn, cur


def test_wa_conversations_messages_analytics(wa):
    conn, cur = _db_conn(fetchall=[{'id': 1}], fetchone={'total': 2})
    wa.db_connection = conn
    assert wa.get_conversations(10, 5) == [{'id': 1}]
    assert wa.get_messages('wid') == [{'id': 1}]
    # analytics: three queries, two fetchall + one fetchone
    cur.fetchall.side_effect = [[{'direction': 'out'}], [{'date': 'd'}]]
    cur.fetchone.return_value = {'total_conversations': 3}
    an = wa.get_analytics(datetime(2026, 1, 1), datetime(2026, 2, 1))
    assert an['conversation_statistics'] == {'total_conversations': 3}

    # error branches
    wa.db_connection = None
    assert wa.get_conversations() == []
    assert wa.get_messages('x') == []
    assert wa.get_analytics(datetime(2026, 1, 1), datetime(2026, 2, 1)) == {}


def test_wa_create_template(wa):
    conn, cur = _db_conn(fetchone=[42])
    wa.db_connection = conn
    res = wa.create_template('n', 'UTILITY', 'en', [{'x': 1}])
    assert res['success'] is True and res['template_id'] == 42
    cur.execute.side_effect = RuntimeError('sql')
    res = wa.create_template('n', 'UTILITY', 'en', [])
    assert res['success'] is False
    conn.rollback.assert_called()
    # no connection at all
    wa.db_connection = None
    res = wa.create_template('n', 'UTILITY', 'en', [])
    assert res['success'] is False


def test_wa_store_message(wa):
    conn, cur = _db_conn()
    wa.db_connection = conn
    wa._store_message('m', 'w', 'text', {'a': 1}, 'outbound', 'sent')
    conn.commit.assert_called_once()
    cur.execute.side_effect = RuntimeError('sql')
    wa._store_message('m', 'w', 'text', {}, 'outbound', 'sent')
    conn.rollback.assert_called()


# ============================================================================
# WhatsAppBusinessIntegration — Flask route handlers (direct calls)
# ============================================================================

class _FlaskReq:
    method = 'GET'

    def __init__(self, method='GET', json_data=None, args=None, headers=None,
                 data=b''):
        self.method = method
        self._json = json_data
        self.args = args or {}
        self.headers = headers or {}
        self._data = data

    def get_json(self):
        if self._json is not None:
            return self._json
        if self._data:
            return json.loads(self._data)
        raise RuntimeError('no json')

    def get_data(self):
        return self._data


def _jsonify(*a, **kw):
    return {'payload': a, 'kw': kw}


def test_flask_health_route():
    with patch.object(wa_mod, 'request', _FlaskReq()), \
            patch.object(wa_mod, 'jsonify', _jsonify):
        wa_mod.whatsapp_integration.access_token = 'tok'
        assert flask_health()['payload'][0]['status'] == 'healthy'
        wa_mod.whatsapp_integration.access_token = None
        res = flask_health()
        assert isinstance(res, tuple) and res[1] == 503


def test_flask_send_route():
    req = _FlaskReq(json_data={'to': '1', 'type': 'text', 'content': {},
                               'user_id': 'u'})
    with patch.object(wa_mod, 'request', req), \
            patch.object(wa_mod, 'jsonify', _jsonify):
        wa_mod.whatsapp_integration.send_message = AsyncMock(
            return_value={'success': True})
        res = asyncio.get_event_loop().run_until_complete(flask_send())
        assert res['payload'][0]['success'] is True
        # missing fields
        req2 = _FlaskReq(json_data={'to': '1'})
        with patch.object(wa_mod, 'request', req2):
            res = asyncio.get_event_loop().run_until_complete(flask_send())
            assert res[1] == 400
        # exception branch
        req3 = _FlaskReq()  # get_json raises
        with patch.object(wa_mod, 'request', req3):
            res = asyncio.get_event_loop().run_until_complete(flask_send())
            assert res[1] == 500


def test_flask_conversations_messages_routes():
    with patch.object(wa_mod, 'jsonify', _jsonify):
        req = _FlaskReq(args={'limit': '5', 'offset': '2'})
        with patch.object(wa_mod, 'request', req):
            wa_mod.whatsapp_integration.get_conversations = \
                MagicMock(return_value=[{'id': 1}])
            res = flask_conversations()
            assert res['payload'][0]['success'] is True
        req = _FlaskReq(args={})
        with patch.object(wa_mod, 'request', req):
            wa_mod.whatsapp_integration.get_messages = \
                MagicMock(return_value=[{'id': 'm'}])
            res = flask_messages('wid')
            assert res['payload'][0]['total'] == 1
            wa_mod.whatsapp_integration.get_messages = MagicMock(
                side_effect=RuntimeError('x'))
            assert flask_messages('wid')[1] == 500
        # int() failure branch
        bad = _FlaskReq(args={'limit': 'abc'})
        with patch.object(wa_mod, 'request', bad):
            assert flask_conversations()[1] == 500
            assert flask_messages('w')[1] == 500


def test_flask_template_analytics_routes():
    with patch.object(wa_mod, 'jsonify', _jsonify):
        req = _FlaskReq(json_data={'template_name': 'n', 'category': 'UTILITY',
                                   'language_code': 'en', 'components': []})
        with patch.object(wa_mod, 'request', req):
            wa_mod.whatsapp_integration.create_template = \
                MagicMock(return_value={'success': True})
            assert flask_create_template()['payload'][0]['success'] is True
        req2 = _FlaskReq(json_data={'template_name': 'n'})
        with patch.object(wa_mod, 'request', req2):
            assert flask_create_template()[1] == 400
        req3 = _FlaskReq()  # json raises
        with patch.object(wa_mod, 'request', req3):
            assert flask_create_template()[1] == 500

        req = _FlaskReq(args={'start_date': '2026-01-01T00:00:00',
                              'end_date': '2026-02-01T00:00:00'})
        with patch.object(wa_mod, 'request', req):
            wa_mod.whatsapp_integration.get_analytics = \
                MagicMock(return_value={'x': 1})
            res = flask_analytics()
            assert res['payload'][0]['success'] is True
        with patch.object(wa_mod, 'request', _FlaskReq(args={})):
            res = flask_analytics()  # default dates
            assert res['payload'][0]['success'] is True
        bad = _FlaskReq(args={'start_date': 'not-a-date'})
        with patch.object(wa_mod, 'request', bad):
            assert flask_analytics()[1] == 500


def _signed(secret, body):
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return {'X-Hub-Signature-256': f'sha256={sig}'}


def test_flask_webhook_get():
    with patch.object(wa_mod, 'request', _FlaskReq()), \
            patch.object(wa_mod, 'jsonify', _jsonify):
        wa_mod.whatsapp_integration.webhook_verify_token = 'vtok'
        req = _FlaskReq(args={'hub.mode': 'subscribe',
                              'hub.verify_token': 'vtok',
                              'hub.challenge': 'ch'})
        with patch.object(wa_mod, 'request', req):
            assert flask_webhook() == ('ch', 200)
        # wrong token
        req.args = {'hub.mode': 'subscribe', 'hub.verify_token': 'nope',
                    'hub.challenge': 'ch'}
        with patch.object(wa_mod, 'request', req):
            assert flask_webhook() == ('Verification failed', 403)
        # unconfigured token fails closed
        wa_mod.whatsapp_integration.webhook_verify_token = None
        req.args = {'hub.mode': 'subscribe', 'hub.verify_token': 'None',
                    'hub.challenge': 'ch'}
        with patch.object(wa_mod, 'request', req):
            assert flask_webhook()[1] == 403


def test_flask_webhook_post():
    secret = 'shhh'
    wa_mod.whatsapp_integration.webhook_app_secret = secret
    wa_mod.whatsapp_integration._store_message = MagicMock()

    body = json.dumps({'entry': [{'changes': [{'value': {
        'messages': [{'id': 'm1', 'from': 'w1', 'type': 'text',
                      'text': {'body': 'hi'}}]}}]}]}).encode()

    # no secret configured -> 503
    wa_mod.whatsapp_integration.webhook_app_secret = None
    with patch.object(wa_mod, 'request',
                      _FlaskReq(method='POST', data=body)):
        assert flask_webhook() == ('Webhook not configured', 503)
    wa_mod.whatsapp_integration.webhook_app_secret = secret

    # missing signature
    with patch.object(wa_mod, 'request', _FlaskReq(method='POST', data=body)):
        assert flask_webhook() == ('Invalid signature', 401)
    # wrong signature
    with patch.object(wa_mod, 'request',
                      _FlaskReq(method='POST', data=body,
                                headers={'X-Hub-Signature-256': 'sha256=bad'})):
        assert flask_webhook() == ('Invalid signature', 401)
    # valid signature (hex + base64 variants)
    loop = MagicMock()
    loop.is_running.return_value = False
    run_calls = []
    with patch.object(wa_mod, 'request',
                      _FlaskReq(method='POST', data=body, headers=_signed(secret, body))), \
            patch.object(wa_mod.asyncio, 'get_event_loop', return_value=loop), \
            patch.object(wa_mod.asyncio, 'run',
                         side_effect=lambda c: run_calls.append(c)):
        assert flask_webhook() == ('ok', 200)
    wa_mod.whatsapp_integration._store_message.assert_called_once()
    b64sig = base64.b64encode(
        hmac.new(secret.encode(), body, hashlib.sha256).digest()).decode()
    with patch.object(wa_mod, 'request',
                      _FlaskReq(method='POST', data=body,
                                headers={'X-Hub-Signature-256':
                                         f'sha256={b64sig}'})), \
            patch.object(wa_mod.asyncio, 'get_event_loop',
                         return_value=loop), \
            patch.object(wa_mod.asyncio, 'run', lambda c: None):
        assert flask_webhook() == ('ok', 200)
    # exception branch
    with patch.object(wa_mod, 'request',
                      _FlaskReq(method='POST', data=b'notjson',
                                headers=_signed(secret, b'notjson'))), \
            patch.object(wa_mod.asyncio, 'get_event_loop', return_value=loop), \
            patch.object(wa_mod.asyncio, 'run', lambda c: None):
        assert flask_webhook() == ('error', 500)


def test_process_incoming_message_types():
    store = MagicMock()
    wa_mod.whatsapp_integration._store_message = store
    bridge = MagicMock()
    bridge.process_incoming_message = AsyncMock()
    loop = MagicMock()
    loop.is_running.return_value = True
    with patch('integrations.universal_webhook_bridge.'
               'universal_webhook_bridge', bridge), \
            patch.object(wa_mod.asyncio, 'get_event_loop', return_value=loop):
        for msg_type, payload in [
            ('text', {'text': {'body': 'b'}}),
            ('image', {'image': {'id': 'i', 'caption': 'c'}}),
            ('audio', {'audio': {'id': 'a'}}),
            ('document', {'document': {'id': 'd', 'filename': 'f'}}),
            ('other', {}),
        ]:
            _process_incoming_message(
                {'id': 'm', 'from': 'w', 'type': msg_type, **payload})
        assert store.call_count == 5
        # loop running -> create_task path
        loop.create_task.assert_called()
        # loop not running -> asyncio.run path
        loop.is_running.return_value = False
        with patch.object(wa_mod.asyncio, 'run', lambda c: None):
            _process_incoming_message({'id': 'm', 'from': 'w', 'type': 'text'})
        # get_event_loop raises RuntimeError -> asyncio.run fallback
        with patch.object(wa_mod.asyncio, 'get_event_loop',
                          side_effect=RuntimeError('no loop')), \
                patch.object(wa_mod.asyncio, 'run', lambda c: None):
            _process_incoming_message({'id': 'm', 'type': 'text'})
        # bridge import/route failure swallowed
        with patch('integrations.universal_webhook_bridge.'
                   'universal_webhook_bridge',
                   side_effect=ImportError('x')):
            _process_incoming_message({'id': 'm', 'type': 'text'})
        # outer exception swallowed
        wa_mod.whatsapp_integration._store_message = MagicMock(
            side_effect=RuntimeError('x'))
        _process_incoming_message({'id': 'm', 'type': 'text'})
    wa_mod.whatsapp_integration._store_message = store


def test_initialize_whatsapp_integration():
    app = MagicMock()
    wa_mod.whatsapp_integration.initialize = MagicMock(return_value=True)
    initialize_whatsapp_integration(app, {})  # bp None -> warning branch
    wa_mod.whatsapp_integration.initialize = MagicMock(return_value=False)
    initialize_whatsapp_integration(app, {})
    wa_mod.whatsapp_integration.initialize = MagicMock(
        side_effect=RuntimeError('x'))
    initialize_whatsapp_integration(app, {})  # exception branch


# ============================================================================
# HubSpotService
# ============================================================================

@pytest.fixture()
def hs():
    svc = HubSpotService(tenant_id='t1', config={'access_token': 'hs-tok'})
    svc.http = MagicMock()
    return svc


async def test_hs_capabilities_ops_close(hs):
    caps = hs.get_capabilities()
    assert caps['supports_webhooks'] is True
    ops = hs.get_operations()
    assert len(ops) == 3
    hs.client = MagicMock()
    hs.client.aclose = AsyncMock()
    await hs.close()
    hs.client.aclose.assert_awaited_once()


async def test_hs_execute_operation_dispatch(hs):
    hs.get_contacts = AsyncMock(return_value=[{'id': 'c'}])
    hs.get_companies = AsyncMock(return_value=[{'id': 'co'}])
    hs.get_deals = AsyncMock(return_value=[{'id': 'd'}])
    hs.create_contact = AsyncMock(return_value={'id': 'nc'})
    hs.search_content = AsyncMock(return_value={'found': 1})

    assert (await hs.execute_operation(
        'get_contacts', {}))['success'] is True
    assert (await hs.execute_operation('list_contacts', {}))['success'] is True
    assert (await hs.execute_operation('get_companies', {}))['success'] is True
    assert (await hs.execute_operation('get_deals', {}))['success'] is True
    assert (await hs.execute_operation(
        'create_contact', {'email': 'a@b.c'}))['success'] is True
    assert (await hs.execute_operation(
        'search_content', {'query': 'q'}))['success'] is True
    # unsupported
    res = await hs.execute_operation('bogus', {})
    assert res['success'] is False
    # tenant mismatch
    res = await hs.execute_operation('get_contacts', {},
                                     context={'tenant_id': 'other'})
    assert res['success'] is False
    # exception path
    hs.get_contacts = AsyncMock(side_effect=RuntimeError('x'))
    res = await hs.execute_operation('get_contacts', {})
    assert res['success'] is False


async def test_hs_entity_operation(hs):
    hs.get_contact = AsyncMock(return_value={'id': 'c'})
    hs.get_company = AsyncMock(return_value={'id': 'co'})
    hs.get_deal = AsyncMock(return_value={'id': 'd'})
    hs.create_company = AsyncMock(return_value={'id': 'nco'})
    hs.create_deal = AsyncMock(return_value={'id': 'nd'})

    ctx = {'token': 'ctx-tok'}
    assert (await hs.execute_entity_operation(
        'get', 'contact', {'contact_id': '1'}, ctx))['success'] is True
    hs.get_contact.assert_awaited_once_with(token='ctx-tok', contact_id='1')
    assert (await hs.execute_entity_operation(
        'get', 'companies', {'company_id': '2'}, None))['success'] is True
    assert (await hs.execute_entity_operation(
        'get', 'deals', {'deal_id': '3'}, None))['success'] is True
    assert (await hs.execute_entity_operation(
        'create', 'company', {'name': 'N'}, None))['success'] is True
    assert (await hs.execute_entity_operation(
        'create', 'deal', {'name': 'D', 'amount': 5}, None))['success'] is True
    # 'ies' -> 'y' normalization
    assert (await hs.execute_entity_operation(
        'get', 'companies', {'company_id': '1'}, None))['success'] is True
    # unsupported operation
    res = await hs.execute_entity_operation('delete', 'contact', {}, None)
    assert res['success'] is False
    # unsupported entity
    res = await hs.execute_entity_operation('get', 'ticket', {}, None)
    assert res['success'] is False
    # exception
    hs.get_contact = AsyncMock(side_effect=RuntimeError('x'))
    res = await hs.execute_entity_operation('get', 'contact', {}, None)
    assert res['success'] is False


async def test_hs_oauth_authenticate(hs):
    hs.http.post = AsyncMock(return_value=_resp(200, {'access_token': 'new'}))
    data = await hs.authenticate('cid', 'sec', 'http://red', 'code')
    assert data['access_token'] == 'new'
    assert hs.access_token == 'new'
    # http error -> 400
    import httpx
    hs.http.post = AsyncMock(side_effect=httpx.HTTPError('net'))
    with pytest.raises(Exception) as ei:
        await hs.authenticate('cid', 'sec', 'r', 'c')
    assert ei.value.status_code == 400
    # unexpected -> 500
    hs.http.post = AsyncMock(side_effect=RuntimeError('x'))
    with pytest.raises(Exception) as ei:
        await hs.authenticate('cid', 'sec', 'r', 'c')
    assert ei.value.status_code == 500


async def test_hs_list_getters(hs, monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs.http.get = AsyncMock(return_value=_resp(200, {'results': [{'id': 1}]}))
    assert await hs.get_contacts() == [{'id': 1}]
    assert await hs.get_contacts(limit=5, offset=10) == [{'id': 1}]
    assert await hs.get_companies(offset=3) == [{'id': 1}]
    assert await hs.get_deals() == [{'id': 1}]
    hs.http.get = AsyncMock(
        return_value=_resp(200, {'campaigns': [{'id': 'cmp'}]}))
    assert await hs.get_campaigns() == [{'id': 'cmp'}]

    # unauthenticated
    hs.access_token = None
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await hs.get_contacts(token=None)
    with pytest.raises(HTTPException):
        await hs.get_companies()
    with pytest.raises(HTTPException):
        await hs.get_deals()
    with pytest.raises(HTTPException):
        await hs.get_campaigns()

    # http error -> 400
    hs.access_token = 'tok'
    import httpx
    for getter, kwargs in (
            (hs.get_contacts, {}), (hs.get_companies, {}),
            (hs.get_deals, {}), (hs.get_campaigns, {})):
        hs.http.get = AsyncMock(side_effect=httpx.HTTPError('net'))
        with pytest.raises(HTTPException):
            await getter(**kwargs)


async def test_hs_search_content(hs, monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs.http.post = AsyncMock(return_value=_resp(200, {'total': 2}))
    assert (await hs.search_content('q'))['total'] == 2
    hs.access_token = None
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await hs.search_content('q')
    hs.access_token = 'tok'
    import httpx
    hs.http.post = AsyncMock(side_effect=httpx.HTTPError('net'))
    with pytest.raises(HTTPException):
        await hs.search_content('q')


async def test_hs_creates(hs, monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs.http.post = AsyncMock(return_value=_resp(201, {'id': 'new'}))
    assert (await hs.create_contact('a@b.c', first_name='A',
                                    phone='1'))['id'] == 'new'
    assert (await hs.create_company('N', domain='d.com'))['id'] == 'new'
    assert (await hs.create_deal('D', 100.0, company_id='co1'))['id'] == 'new'

    from fastapi import HTTPException
    hs.access_token = None
    with pytest.raises(HTTPException):
        await hs.create_contact('a@b.c')
    with pytest.raises(HTTPException):
        await hs.create_company('N')
    with pytest.raises(HTTPException):
        await hs.create_deal('D', 1)

    import httpx
    hs.access_token = 'tok'
    hs.http.post = AsyncMock(side_effect=httpx.HTTPError('net'))
    for fn, args in ((hs.create_contact, ('a@b.c',)),
                     (hs.create_company, ('N',)),
                     (hs.create_deal, ('D', 1))):
        with pytest.raises(HTTPException):
            await fn(*args)


async def test_hs_get_update_object(hs, monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs.http.get = AsyncMock(return_value=_resp(200, {'id': 'x'}))
    assert (await hs.get_contact('c1'))['id'] == 'x'
    assert (await hs.get_company('co1'))['id'] == 'x'
    assert (await hs.get_deal('d1'))['id'] == 'x'
    hs.http.patch = AsyncMock(return_value=_resp(200, {'id': 'upd'}))
    assert (await hs.update_contact('c1', {'a': 1}))['id'] == 'upd'
    assert (await hs.update_deal('d1', {'b': 2}))['id'] == 'upd'

    from fastapi import HTTPException
    import httpx
    hs.access_token = None
    with pytest.raises(HTTPException):
        await hs.get_object('contacts', '1')
    hs.access_token = 'tok'
    hs.http.get = AsyncMock(side_effect=httpx.HTTPError('net'))
    hs.http.patch = AsyncMock(side_effect=httpx.HTTPError('net'))
    with pytest.raises(HTTPException):
        await hs.get_object('contacts', '1')
    with pytest.raises(HTTPException):
        await hs.update_object('contacts', '1', {})
    monkeypatch.setenv('HUBSPOT_ACCESS_TOKEN', 'envtok')
    hs.access_token = None
    hs.http.patch = AsyncMock(return_value=_resp(200, {'id': 'env'}))
    assert (await hs.update_object('contacts', '1', {}))['id'] == 'env'


async def test_hs_analytics_and_properties(hs, monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs.get_deals = AsyncMock(return_value=[
        {'properties': {'amount': '100'}}, {'properties': {'amount': None}}])
    hs.http.post = AsyncMock(return_value=_resp(200, {'total': 7}))
    an = await hs.get_analytics()
    assert an['total_revenue'] == 100.0 and an['contact_count'] == 7
    # non-200 contact search -> count 0
    hs.http.post = AsyncMock(return_value=_resp(500, {}))
    assert (await hs.get_analytics())['contact_count'] == 0
    # unauthenticated
    hs.access_token = None
    assert (await hs.get_analytics())['error'] == 'Not authenticated'
    # exception
    hs.access_token = 'tok'
    hs.get_deals = AsyncMock(side_effect=RuntimeError('x'))
    assert 'error' in await hs.get_analytics()

    hs.http.get = AsyncMock(return_value=_resp(200, {'results': [{'p': 1}]}))
    assert await hs.get_properties('contacts') == [{'p': 1}]
    hs.access_token = None
    assert await hs.get_properties('contacts') == []  # 401 caught -> []
    hs.access_token = 'tok'
    hs.http.get = AsyncMock(side_effect=RuntimeError('x'))
    assert await hs.get_properties('contacts') == []


async def test_hs_health(hs):
    assert (await hs.health_check())['ok'] is True


async def test_hs_sync_to_postgres_cache(hs, monkeypatch):
    hs.get_analytics = AsyncMock(return_value={
        'contact_count': 3, 'deal_count': 2, 'total_revenue': 50.0})
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal',
                        MagicMock(return_value=db))
    res = await hs.sync_to_postgres_cache('ws1')
    assert res == {'success': True, 'metrics_synced': 3}
    db.add.assert_called()
    db.commit.assert_called_once()

    # update existing path
    db.query.return_value.filter_by.return_value.first.return_value = \
        MagicMock()
    assert (await hs.sync_to_postgres_cache('ws1'))['metrics_synced'] == 3

    # inner save failure
    db.commit = MagicMock(side_effect=RuntimeError('x'))
    res = await hs.sync_to_postgres_cache('ws1')
    assert res['success'] is False
    db.rollback.assert_called()

    # analytics failure -> outer exception
    hs.get_analytics = AsyncMock(return_value={'error': 'x'})
    monkeypatch.setattr('core.database.SessionLocal',
                        MagicMock(side_effect=RuntimeError('no db')))
    res = await hs.sync_to_postgres_cache('ws1')
    assert res['success'] is False


async def test_hs_full_sync(hs):
    hs.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 1})
    res = await hs.full_sync('ws1')
    assert res['success'] is True


def test_get_hubspot_service(monkeypatch):
    monkeypatch.delenv('HUBSPOT_ACCESS_TOKEN', raising=False)
    hs_mod._hubspot_service_singleton = None
    assert get_hubspot_service() is None
    monkeypatch.setenv('HUBSPOT_ACCESS_TOKEN', 'env-token')
    svc = get_hubspot_service()
    assert svc.access_token == 'env-token'
    assert get_hubspot_service() is svc  # cached singleton
    hs_mod._hubspot_service_singleton = None


# ============================================================================
# FastAPI routes
# ============================================================================

@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(wfr.router)
    app.dependency_overrides[get_current_user] = lambda: {'id': 'u1', 'sub': 'u1'}
    with patch.object(wfr, 'whatsapp_integration', MagicMock()) as integ, \
            patch.object(wfr, 'whatsapp_service_manager', MagicMock()) as mgr:
        mgr.config = {}
        yield TestClient(app), integ, mgr
    app.dependency_overrides.clear()


def test_route_health(client):
    c, integ, mgr = client
    mgr.config = {'x': 1}
    assert c.get('/api/whatsapp/health').json()['status'] == 'healthy'
    mgr.config = {}
    assert c.get('/api/whatsapp/health').status_code == 503
    # unexpected exception branch
    type(mgr).config = property(
        lambda s: (_ for _ in ()).throw(RuntimeError('x')))
    assert c.get('/api/whatsapp/health').status_code == 500
    del type(mgr).config


def test_route_service_health_metrics_init(client):
    c, integ, mgr = client
    mgr.health_check = MagicMock(return_value={'status': 'healthy'})
    assert c.get('/api/whatsapp/service/health').json()['status'] == 'healthy'
    mgr.health_check = MagicMock(return_value={'status': 'down',
                                               'detail': 'd'})
    assert c.get('/api/whatsapp/service/health').status_code == 503
    mgr.health_check = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/service/health').status_code == 500

    mgr.get_service_metrics = MagicMock(return_value={'sent': 1})
    assert c.get('/api/whatsapp/service/metrics').json() == {'sent': 1}
    mgr.get_service_metrics = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/service/metrics').status_code == 500

    mgr.initialize_service = MagicMock(return_value={'success': True})
    assert c.post('/api/whatsapp/service/initialize').json()['success'] is True
    mgr.initialize_service = MagicMock(side_effect=RuntimeError('x'))
    assert c.post('/api/whatsapp/service/initialize').status_code == 500


def test_route_send(client):
    c, integ, mgr = client
    integ.send_message = MagicMock(return_value={'success': True,
                                                 'message_id': 'm'})
    r = c.post('/api/whatsapp/send', json={
        'to': '123', 'type': 'text', 'content': {'text': 'hi'}})
    assert r.json()['success'] is True
    # validation error -> 422
    assert c.post('/api/whatsapp/send', json={'to': '1'}).status_code == 422

    r = c.post('/api/whatsapp/messages',
               json={'to': '123', 'message': 'hi', 'type': 'text'})
    assert r.status_code == 200
    r = c.post('/api/whatsapp/messages',
               json={'to': '123', 'message': 'hi', 'type': 'other'})
    assert r.status_code == 200  # content {"body": ...} branch
    integ.send_message = MagicMock(side_effect=RuntimeError('x'))
    assert c.post('/api/whatsapp/send', json={
        'to': '1', 'type': 'text', 'content': {}}).status_code == 500


def test_route_batch(client):
    c, integ, mgr = client
    integ.send_message = MagicMock(
        side_effect=[{'success': True, 'message_id': 'm1'},
                     RuntimeError('boom')])
    r = c.post('/api/whatsapp/send/batch', json={
        'recipients': ['1', '2'], 'message': {'text': 'hi'},
        'type': 'text', 'delay_between_messages': 0})
    body = r.json()
    assert body['success_count'] == 1 and body['failure_count'] == 1
    assert body['results'][1]['success'] is False


def test_route_conversations(client):
    c, integ, mgr = client
    integ.get_conversations = MagicMock(return_value=[{'id': 1}])
    r = c.get('/api/whatsapp/conversations?limit=10')
    assert r.json()['total'] == 1
    integ.get_conversations = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/conversations').status_code == 500


def test_route_search_conversations(client):
    c, integ, mgr = client
    # no params -> 400
    assert c.get('/api/whatsapp/conversations/search').status_code == 400

    convs = [
        {'name': 'Alice', 'phone_number': '111', 'status': 'active',
         'last_message_at': '2026-01-02T00:00:00'},
        {'name': 'Bob', 'phone_number': '222', 'status': 'closed',
         'last_message_at': '2025-01-01T00:00:00'},
    ]
    integ.get_conversations = MagicMock(return_value=convs)
    r = c.get('/api/whatsapp/conversations/search?query=alice')
    assert r.json()['pagination']['total'] == 1
    r = c.get('/api/whatsapp/conversations/search?status=closed')
    assert r.json()['pagination']['total'] == 1
    r = c.get('/api/whatsapp/conversations/search'
              '?date_from=2026-01-01T00:00:00')
    assert r.json()['pagination']['total'] == 1
    r = c.get('/api/whatsapp/conversations/search?date_to=2025-06-01T00:00:00')
    assert r.json()['pagination']['total'] == 1
    # invalid stored date -> skipped
    r = c.get('/api/whatsapp/conversations/search?date_from=2026-01-01')
    assert r.status_code == 200
    integ.get_conversations = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/conversations/search?query=x').status_code == 500


def test_route_messages(client):
    c, integ, mgr = client
    integ.get_messages = MagicMock(return_value=[{'id': 'm'}])
    r = c.get('/api/whatsapp/messages/wid')
    assert r.json()['total'] == 1
    integ.get_messages = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/messages/wid').status_code == 500

    integ.get_conversations = MagicMock(return_value=[
        {'whatsapp_id': 'w1', 'phone_number': '111',
         'last_message': 'hi', 'last_message_at': '2026-01-01'},
        {'whatsapp_id': 'w2'}])
    r = c.get('/api/whatsapp/messages')
    body = r.json()
    assert body['total'] == 1 and body['messages'][0]['id'] == 'msg_w1'
    integ.get_conversations = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/messages').status_code == 500


def test_route_templates(client):
    c, integ, mgr = client
    integ.create_template = MagicMock(return_value={'success': True})
    r = c.post('/api/whatsapp/templates', json={
        'template_name': 'n', 'category': 'UTILITY', 'language_code': 'en',
        'components': [{'x': 1}]})
    assert r.json()['success'] is True
    integ.create_template = MagicMock(side_effect=RuntimeError('x'))
    assert c.post('/api/whatsapp/templates', json={
        'template_name': 'n', 'category': 'U', 'language_code': 'en',
        'components': []}).status_code == 500


def test_route_analytics(client):
    c, integ, mgr = client
    integ.get_analytics = MagicMock(return_value={'x': 1})
    r = c.get('/api/whatsapp/analytics?start_date=2026-01-01T00:00:00')
    assert r.json()['success'] is True
    assert c.get('/api/whatsapp/analytics').status_code == 200
    integ.get_analytics = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/analytics').status_code == 500

    # export json
    integ.get_analytics = MagicMock(return_value={'x': 1})
    r = c.get('/api/whatsapp/analytics/export?format=json')
    assert r.json()['format'] == 'json'
    # export csv
    integ.get_analytics = MagicMock(return_value={
        'message_statistics': [{'message_type': 'text', 'direction': 'in',
                                'status': 'sent', 'count': 3}]})
    r = c.get('/api/whatsapp/analytics/export?format=csv')
    assert r.headers['content-type'].startswith('text/csv')
    assert 'text,in,sent,3' in r.text
    # invalid format pattern
    assert c.get('/api/whatsapp/analytics/export?format=xml').status_code == 422
    integ.get_analytics = MagicMock(side_effect=RuntimeError('x'))
    assert c.get('/api/whatsapp/analytics/export').status_code == 500


def test_route_business_profile(client):
    c, integ, mgr = client
    mgr.config = {}
    r = c.get('/api/whatsapp/configuration/business-profile')
    assert r.json()['success'] is True
    mgr.get_config = MagicMock()  # unused; keep config dict simple

    # missing fields -> 400
    r = c.put('/api/whatsapp/configuration/business-profile',
              json={'business_profile': {'name': 'N'}})
    assert r.status_code == 400
    # ok update
    r = c.put('/api/whatsapp/configuration/business-profile',
              json={'business_profile': {'name': 'N', 'description': 'D',
                                         'email': 'e@x.y'}})
    assert r.json()['success'] is True
    assert mgr.config['business_profile']['name'] == 'N'
    # exception branch
    type(mgr).config = property(
        lambda s: (_ for _ in ()).throw(RuntimeError('x')))
    r = c.put('/api/whatsapp/configuration/business-profile',
              json={'business_profile': {'name': 'N', 'description': 'D',
                                         'email': 'e'}})
    assert r.status_code == 500
    del type(mgr).config


def test_route_webhook_verification(client, monkeypatch):
    c, integ, mgr = client
    monkeypatch.delenv('WHATSAPP_VERIFY_TOKEN', raising=False)
    integ.webhook_verify_token = 'vtok'
    r = c.get('/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=vtok'
              '&hub.challenge=ch123')
    assert r.status_code == 200 and r.text == '"ch123"'
    # wrong token
    r = c.get('/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=bad'
              '&hub.challenge=ch')
    assert r.status_code == 403
    # env var wins
    monkeypatch.setenv('WHATSAPP_VERIFY_TOKEN', 'envtok')
    r = c.get('/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=envtok'
              '&hub.challenge=ch2')
    assert r.status_code == 200
    # unconfigured fails closed
    monkeypatch.delenv('WHATSAPP_VERIFY_TOKEN', raising=False)
    integ.webhook_verify_token = None
    r = c.get('/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=None'
              '&hub.challenge=ch')
    assert r.status_code == 403


def test_route_webhook_handler(client, monkeypatch):
    c, integ, mgr = client
    monkeypatch.delenv('WHATSAPP_APP_SECRET', raising=False)
    integ.webhook_app_secret = None
    r = c.post('/api/whatsapp/webhook', json={'x': 1})
    assert r.status_code == 503

    secret = 'shh'
    integ.webhook_app_secret = secret
    body = json.dumps({'entry': []}).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    # missing signature
    r = c.post('/api/whatsapp/webhook', content=body,
               headers={'Content-Type': 'application/json'})
    assert r.status_code == 401
    # bad signature
    r = c.post('/api/whatsapp/webhook', content=body,
               headers={'X-Hub-Signature-256': 'sha256=bad'})
    assert r.status_code == 401

    bridge = MagicMock()
    bridge.process_incoming_message = AsyncMock()
    with patch('integrations.universal_webhook_bridge.'
               'universal_webhook_bridge', bridge):
        r = c.post('/api/whatsapp/webhook', content=body,
                   headers={'X-Hub-Signature-256': f'sha256={sig}'})
        assert r.status_code == 200
        # invalid JSON -> 500 branch
        bad = b'not-json'
        bsig = hmac.new(secret.encode(), bad, hashlib.sha256).hexdigest()
        r = c.post('/api/whatsapp/webhook', content=bad,
                   headers={'X-Hub-Signature-256': f'sha256={bsig}'})
        assert r.status_code == 500


def test_register_and_initialize_helpers(client, monkeypatch):
    app = MagicMock()
    assert wfr.register_whatsapp_routes(app) is True
    with patch.object(wfr, 'whatsapp_service_manager') as mgr:
        mgr.initialize_service = MagicMock(return_value={'success': True})
        assert wfr.initialize_whatsapp_service() is True
    with patch.object(wfr, 'WHATSAPP_AVAILABLE', False):
        assert wfr.register_whatsapp_routes(app) is False
        assert wfr.initialize_whatsapp_service() is False
    with patch.object(wfr, 'whatsapp_service_manager') as mgr:
        mgr.initialize_service = MagicMock(side_effect=RuntimeError('x'))
        assert wfr.initialize_whatsapp_service() is False


def test_websocket_routes_registered():
    app = FastAPI()
    wfr.register_whatsapp_routes(app)
    app.dependency_overrides[get_current_user] = lambda: {'id': 'u'}
    c = TestClient(app)
    r = c.get('/api/whatsapp/websocket/status')
    assert r.json()['status'] == 'available'
    r = c.post('/api/whatsapp/websocket/notify', json={'type': 't'})
    assert r.json()['success'] is True
