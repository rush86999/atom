# -*- coding: utf-8 -*-
"""Coverage wave 87 — integrations.freshdesk_service, trello_service,
shopify_service.

No network: httpx/requests boundaries, IntegrationHTTP and DB sessions are
mocked.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import integrations.freshdesk_service as fd_mod
from integrations.freshdesk_service import (
    FreshdeskConfig,
    FreshdeskConstants,
    FreshdeskService,
    create_freshdesk_service,
    get_freshdesk_service,
    )
from integrations.freshdesk_service import \
    test_freshdesk_connection as fd_test_connection
import integrations.trello_service as tr_mod
from integrations.trello_service import TrelloService
import integrations.shopify_service as sh_mod
from integrations.shopify_service import ShopifyService


def _resp(payload=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    r.text = 'body'
    return r


def _async_resp(payload=None, status=200):
    r = _resp(payload, status)
    r.aresp = True
    return r


# ============================================================================
# FreshdeskService
# ============================================================================

@pytest.fixture()
def fd(monkeypatch):
    monkeypatch.setenv('FRESHDESK_API_KEY', 'key')
    monkeypatch.setenv('FRESHDESK_DOMAIN', 'dom')
    svc = FreshdeskService(tenant_id='t1', config={})
    svc.client = MagicMock()
    return svc


def _req_fd(svc, payload=None, error=None):
    if payload is None:
        payload = {'id': 1}
    resp = _resp(payload)
    if error:
        resp.raise_for_status.side_effect = error
    svc.client.get = AsyncMock(return_value=resp)
    svc.client.post = AsyncMock(return_value=resp)
    svc.client.put = AsyncMock(return_value=resp)
    svc.client.delete = AsyncMock(return_value=resp)
    return resp


def _status_err():
    return httpx.HTTPStatusError(
        'boom', request=httpx.Request('GET', 'http://x'),
        response=MagicMock())


def _request_err():
    return httpx.RequestError('netfail', request=httpx.Request('GET', 'http://x'))


def test_fd_init_and_capabilities(fd, monkeypatch):
    assert fd.base_url == 'https://dom.freshdesk.com/api/v2'
    assert fd.headers['Authorization'].startswith('Basic ')
    caps = fd.get_capabilities()
    assert caps['supports_webhooks'] is True
    assert len(caps['operations']) == 3
    # no api key -> empty auth header
    monkeypatch.delenv('FRESHDESK_API_KEY', raising=False)
    svc = FreshdeskService(tenant_id='t', config={'freshdesk_domain': 'd'})
    assert svc.headers['Authorization'] == ''
    assert FreshdeskConfig(api_key='k', domain='d').api_version == 'v2'


async def test_fd_crud(fd):
    _req_fd(fd)
    assert await fd.get_tickets(page=2, per_page=5, status='open',
                                priority='high', created_since='2026-01-01') == {'id': 1}
    assert await fd.get_ticket(1) == {'id': 1}
    assert await fd.create_ticket({'subject': 's'}) == {'id': 1}
    assert await fd.update_ticket(1, {}) == {'id': 1}
    assert await fd.delete_ticket(1) is True
    assert await fd.add_ticket_note(1, {}) == {'id': 1}
    assert await fd.get_ticket_conversations(1) == {'id': 1}
    assert await fd.create_contact({}) == {'id': 1}
    assert await fd.get_contacts() == {'id': 1}
    assert await fd.get_contact(1) == {'id': 1}
    assert await fd.update_contact(1, {}) == {'id': 1}
    assert await fd.create_company({}) == {'id': 1}
    assert await fd.get_companies() == {'id': 1}
    assert await fd.get_company(1) == {'id': 1}
    assert await fd.get_agents() == {'id': 1}
    assert await fd.get_agent(1) == {'id': 1}
    assert await fd.get_groups() == {'id': 1}
    assert await fd.get_group(1) == {'id': 1}
    assert await fd.get_tickets_metrics(date_range='7d', group_by='status') == {'id': 1}
    assert await fd.get_satisfaction_ratings(ticket_id=1, date_range='7d') == {'id': 1}
    assert await fd.search_tickets('q', filters={'x': 1}) == {'id': 1}
    assert await fd.search_contacts('q') == {'id': 1}
    assert await fd.get_account_info() == {'id': 1}


async def test_fd_retry_then_success():
    svc = create_freshdesk_service('k', 'd', freshdesk_max_retries=2)
    svc.client = MagicMock()
    resp = _resp({'ok': 1})
    bad = _resp({})
    bad.raise_for_status.side_effect = _status_err()
    svc.client.get = AsyncMock(side_effect=[bad, resp])
    assert await svc.get_ticket(1) == {'ok': 1}

    bad2 = _resp({})
    bad2.raise_for_status.side_effect = _request_err()
    svc.client.get = AsyncMock(side_effect=[bad2, resp])
    assert await svc.get_ticket(1) == {'ok': 1}


async def test_fd_retry_exhausted_raises(fd):
    bad = _resp({})
    bad.raise_for_status.side_effect = _status_err()
    fd.client.get = AsyncMock(return_value=bad)
    with pytest.raises(httpx.HTTPStatusError):
        await fd.get_ticket(1)
    bad2 = _resp({})
    bad2.raise_for_status.side_effect = _request_err()
    fd.client.get = AsyncMock(return_value=bad2)
    with pytest.raises(httpx.RequestError):
        await fd.get_ticket(1)


async def test_fd_execute_operation(fd):
    fd.get_tickets = AsyncMock(return_value=[])
    fd.create_ticket = AsyncMock(return_value={'id': 1})
    fd.search_tickets = AsyncMock(return_value=[])
    assert (await fd.execute_operation('get_tickets', {
        'page': 2, 'per_page': 5, 'status': 'x', 'priority': 'y',
        'created_since': 'z'}))['success'] is True
    assert (await fd.execute_operation('create_ticket', {'data': {}}))['success'] is True
    assert (await fd.execute_operation('search_tickets', {'query': 'q'}))['success'] is True
    assert (await fd.execute_operation('bogus', {}))['success'] is False
    assert (await fd.execute_operation(
        'get_tickets', {}, context={'tenant_id': 'other'}))['success'] is False
    fd.get_tickets = AsyncMock(side_effect=RuntimeError('x'))
    res = await fd.execute_operation('get_tickets', {})
    assert res['success'] is False and res['error'] == 'Operation failed'


def test_fd_health_check(fd, monkeypatch):
    import requests as req_mod
    fd.api_key = None
    assert fd.health_check()['healthy'] is False
    fd.api_key = 'k'
    r = MagicMock()
    r.status_code = 200
    r.text = 'ok'
    monkeypatch.setattr(req_mod, 'get', MagicMock(return_value=r))
    assert fd.health_check()['healthy'] is True
    r.status_code = 503
    assert fd.health_check()['healthy'] is False
    monkeypatch.setattr(req_mod, 'get', MagicMock(side_effect=RuntimeError('x')))
    assert fd.health_check()['healthy'] is False


async def test_fd_upload_attachment(fd):
    with patch.object(fd_mod.httpx, 'AsyncClient') as AC:
        up = AC.return_value
        resp = _resp({'id': 'a'})
        up.post = AsyncMock(return_value=resp)
        up.aclose = AsyncMock()
        assert await fd.upload_attachment(b'data', 'f.txt') == {'id': 'a'}
        up.aclose.assert_awaited()


def test_fd_utility_names(fd):
    assert fd.get_status_name(2) == 'Open'
    assert fd.get_status_name(99) == 'Unknown'
    assert fd.get_priority_name(4) == 'Urgent'
    assert fd.get_priority_name(0) == 'Unknown'
    assert FreshdeskConstants.STATUS_OPEN == 2
    assert FreshdeskConstants.MAX_TICKETS_PER_PAGE == 100


async def test_fd_close(fd):
    fd.client.aclose = AsyncMock()
    await fd.close()


async def test_fd_sync_to_postgres_cache(fd, monkeypatch):
    fd.get_tickets = AsyncMock(return_value=[1, 2])
    fd.get_contacts = AsyncMock(side_effect=RuntimeError('x'))
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db))
    res = await fd.sync_to_postgres_cache('w1')
    assert res == {'success': True, 'metrics_synced': 2}

    db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    assert (await fd.sync_to_postgres_cache('w1'))['success'] is True

    db.commit = MagicMock(side_effect=RuntimeError('x'))
    res = await fd.sync_to_postgres_cache('w1')
    assert res['success'] is False

    db2 = MagicMock()
    db2.query.side_effect = RuntimeError('x')
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db2))
    fd.get_contacts = AsyncMock(return_value=[])
    assert (await fd.sync_to_postgres_cache('w1'))['success'] is False


async def test_fd_full_sync(fd):
    fd.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 1})
    assert (await fd.full_sync('w1'))['success'] is True


def test_fd_factories(monkeypatch):
    svc = create_freshdesk_service('k', 'd')
    assert svc.domain == 'd'
    monkeypatch.delenv('FRESHDESK_API_KEY', raising=False)
    monkeypatch.delenv('FRESHDESK_DOMAIN', raising=False)
    assert get_freshdesk_service() is None
    monkeypatch.setenv('FRESHDESK_API_KEY', 'k')
    monkeypatch.setenv('FRESHDESK_DOMAIN', 'd')
    assert get_freshdesk_service() is not None


async def test_fd_test_connection(monkeypatch):
    svc = create_freshdesk_service('k', 'd')
    svc.close = AsyncMock()
    svc.health_check = MagicMock(return_value={'healthy': True})
    assert await fd_test_connection('k', 'd') is True
    svc2 = create_freshdesk_service('k', 'd')
    with patch.object(fd_mod.FreshdeskService, 'health_check',
                      side_effect=RuntimeError('x')):
        assert await fd_test_connection('k', 'd') is False


# ============================================================================
# TrelloService
# ============================================================================

TEN = 'tenant-1234'


@pytest.fixture()
def tr():
    svc = TrelloService(tenant_id=TEN, config={'api_key': 'k', 'access_token': 'tok'})
    svc.session = MagicMock()
    return svc


def _tresp(payload=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    if status >= 400:
        r.raise_for_status.side_effect = RuntimeError('HTTP %d' % status)
    else:
        r.raise_for_status = MagicMock()
    return r


def test_tr_init_disabled(monkeypatch):
    for var in ('TRELLO_API_KEY', 'TRELLO_CLIENT_ID', 'TRELLO_ACCESS_TOKEN'):
        monkeypatch.delenv(var, raising=False)
    svc = TrelloService(tenant_id=TEN, config={})
    assert svc.enabled is False
    with pytest.raises(ValueError):
        svc._make_request('GET', '/x')
    # env-based init
    monkeypatch.setenv('TRELLO_API_KEY', 'ek')
    monkeypatch.setenv('TRELLO_ACCESS_TOKEN', 'et')
    svc2 = TrelloService(tenant_id=TEN, config={})
    assert svc2.enabled is True


def test_tr_make_request(tr):
    tr.session.request.return_value = _tresp([1])
    r = tr._make_request('GET', '/boards', params={'a': 1},
                         token='othertoken')
    assert r.json() == [1]
    args, kwargs = tr.session.request.call_args
    assert kwargs['method'] == 'GET' and kwargs['url'].endswith('/boards')
    assert kwargs['params']['key'] == 'k'
    assert kwargs['params']['token'] == 'othertoken'
    # absolute URL passthrough
    tr._make_request('GET', 'http://example.com/x')
    assert tr.session.request.call_args[1]['url'] == 'http://example.com/x'


def test_tr_test_connection(tr):
    tr._make_request = MagicMock(return_value=_tresp(
        {'username': 'u', 'fullName': 'F'}))
    res = tr.test_connection()
    assert res['status'] == 'success' and res['authenticated'] is True
    tr._make_request = MagicMock(return_value=_tresp({}, status=401))
    assert tr.test_connection()['authenticated'] is False
    tr._make_request = MagicMock(side_effect=RuntimeError('x'))
    assert tr.test_connection()['status'] == 'error'


def test_tr_health_check_and_info(tr):
    tr.test_connection = MagicMock(
        return_value={'status': 'success', 'message': 'ok'})
    hc = tr.health_check()
    assert hc['healthy'] is True
    info = asyncio.run(tr.get_service_info())
    assert info['status'] == 'operational'
    caps = tr.get_capabilities()
    assert caps['supports_webhooks'] is True


def test_tr_boards_lists_cards(tr):
    tr._make_request = MagicMock(return_value=_tresp([{'id': 'b'}]))
    assert tr.get_boards(filter='all', fields=['name']) == [{'id': 'b'}]
    assert tr.get_board('b1', fields=['name']) == [{'id': 'b'}]
    assert tr.create_board('N', 'd', default_lists=False) == [{'id': 'b'}]
    assert tr.get_lists('b1') == [{'id': 'b'}]
    assert tr.create_list('b1', 'L') == [{'id': 'b'}]
    assert tr.get_cards(list_id='l1') == [{'id': 'b'}]
    assert tr.get_cards(board_id='b1') == [{'id': 'b'}]
    assert tr.get_cards() == [{'id': 'b'}]
    assert tr.get_card('c1') == [{'id': 'b'}]
    assert tr.get_cards(list_id='l1', fields=['name'], limit=5)[0] == {'id': 'b'}
    # failures -> empty/None
    tr._make_request = MagicMock(return_value=_tresp({}, status=500))
    assert tr.get_boards() == []
    assert tr.get_board('b1') is None
    assert tr.get_lists('b1') == []
    assert tr.get_cards() == []
    assert tr.get_card('c1') is None
    assert tr.create_board('N') is None
    assert tr.create_list('b1', 'L') is None


def test_tr_card_ops(tr):
    tr._make_request = MagicMock(return_value=_tresp({'id': 'c'}))
    assert tr.create_card('N', 'l1', due='2026-01-01', labels=['a'],
                          members=['m']) == {'id': 'c'}
    assert tr.update_card('c1', {'name': 'x'}) == {'id': 'c'}
    assert tr.archive_card('c1') is True
    assert tr.delete_card('c1') is True
    assert tr.add_comment('c1', 'hi') == {'id': 'c'}
    assert tr.get_comments('c1') == {'id': 'c'}
    assert tr.get_checklists('c1') == {'id': 'c'}
    assert tr.create_checklist('c1', 'chk') == {'id': 'c'}
    assert tr.add_checklist_item('cl1', 'item', checked=True) == {'id': 'c'}
    assert tr.move_card('c1', 'l2') == {'id': 'c'}
    assert tr.get_members('b1', fields=['name']) == {'id': 'c'}
    assert tr.add_member_to_card('c1', 'm1') == {'id': 'c'}
    assert tr.remove_member_from_card('c1', 'm1') is True
    assert tr.get_labels('b1') == {'id': 'c'}
    assert tr.create_label('b1', 'L', color='red') == {'id': 'c'}
    assert tr.add_label_to_card('c1', 'l1') == {'id': 'c'}
    assert tr.remove_label_from_card('c1', 'l1') is True
    assert tr.get_user_profile() == {'id': 'c'}
    assert tr.search('q', board_id='b1') == []  # payload has no 'cards'
    tr._make_request = MagicMock(
        return_value=_tresp({'cards': [{'id': 'c'}]}))
    assert tr.search('q') == [{'id': 'c'}]
    tr._make_request = MagicMock(return_value=_tresp({'id': 'c'}))
    assert tr.get_activities('b1', since='s') == {'id': 'c'}

    # failure branches
    tr._make_request = MagicMock(return_value=_tresp({}, status=500))
    assert tr.create_card('N', 'l1') is None  # implicit None
    assert tr.update_card('c1', {}) is None
    assert tr.archive_card('c1') is False
    assert tr.delete_card('c1') is False
    assert tr.add_comment('c1', 'x') is None
    assert tr.get_comments('c1') == []
    assert tr.get_checklists('c1') == []
    assert tr.create_checklist('c1', 'n') is None
    assert tr.add_checklist_item('cl', 'i') is None
    assert tr.get_members('b1') == []
    assert tr.add_member_to_card('c1', 'm') is None
    assert tr.remove_member_from_card('c1', 'm') is False
    assert tr.get_labels('b1') == []
    assert tr.create_label('b1', 'n') is None
    assert tr.add_label_to_card('c1', 'l') is None
    assert tr.remove_label_from_card('c1', 'l') is False
    assert tr.get_user_profile() is None
    assert tr.search('q') == []
    assert tr.get_activities('b1') == []


def test_tr_search_cards_list(tr):
    tr._make_request = MagicMock(return_value=_tresp({'cards': [{'id': 1}]}))
    assert tr.search('q') == [{'id': 1}]


def test_tr_sync_to_postgres_cache(tr, monkeypatch):
    tr.get_boards = MagicMock(return_value=[{'id': 'b'}])
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db))
    assert tr.sync_to_postgres_cache('w1') == {
        'success': True, 'metrics_synced': 1}
    db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    assert tr.sync_to_postgres_cache('w1')['success'] is True
    db.commit = MagicMock(side_effect=RuntimeError('x'))
    assert tr.sync_to_postgres_cache('w1')['success'] is False
    monkeypatch.setattr('core.database.SessionLocal',
                        MagicMock(side_effect=RuntimeError('x')))
    assert tr.sync_to_postgres_cache('w1')['success'] is False


def test_tr_full_sync(tr):
    tr.sync_to_postgres_cache = MagicMock(
        return_value={'success': True, 'metrics_synced': 1})
    assert tr.full_sync('w1')['success'] is True


async def test_tr_execute_operation(tr):
    tr.create_card = MagicMock(return_value={'id': 'c'})
    tr.get_cards = MagicMock(return_value=[{'id': 'c'}])
    tr.update_card = MagicMock(return_value={'id': 'c'})
    tr.get_boards = MagicMock(return_value=[{'id': 'b'}])
    tr.add_comment = MagicMock(return_value={'id': 'cm'})

    assert (await tr.execute_operation('create_card', {
        'name': 'n', 'list_id': 'l'}))['success'] is True
    assert (await tr.execute_operation('get_cards', {}))['success'] is True
    assert (await tr.execute_operation('update_card', {
        'card_id': 'c', 'name': 'x', 'token': 't'}))['success'] is True
    assert (await tr.execute_operation('get_boards', {}))['success'] is True
    assert (await tr.execute_operation('add_comment', {
        'card_id': 'c', 'text': 'hi'}))['success'] is True
    assert (await tr.execute_operation('nope', {}))['success'] is False
    assert (await tr.execute_operation(
        'get_cards', {}, context={'tenant_id': 'other'}))['success'] is False
    tr.create_card = MagicMock(return_value=None)
    res = await tr.execute_operation('create_card', {})
    assert res['success'] is False and 'Failed' in res['error']


# ============================================================================
# ShopifyService
# ============================================================================

@pytest.fixture()
def sh():
    svc = ShopifyService(tenant_id='t1', config={
        'api_key': 'k', 'api_secret': 's', 'shop_name': 'my-shop'})
    svc.http = MagicMock()
    return svc


def _sh_get(svc, payload=None, status=200):
    resp = _resp(payload, status)
    if status >= 400:
        resp.raise_for_status.side_effect = RuntimeError('http')
    svc.http.get = AsyncMock(return_value=resp)
    svc.http.post = AsyncMock(return_value=resp)
    svc.http.put = AsyncMock(return_value=resp)
    return resp


def test_sh_helpers(sh):
    assert sh._get_base_url('my-shop') == \
        'https://my-shop.myshopify.com/admin/api/2023-10'
    assert sh._get_base_url('x.myshopify.com').startswith('https://x.myshopify')
    assert sh._get_headers('tok')['X-Shopify-Access-Token'] == 'tok'
    caps = sh.get_capabilities()
    assert caps['supports_webhooks'] is True


async def test_sh_health(sh):
    sh.api_key = None
    assert (await sh.health_check())['healthy'] is False
    sh.api_key = 'k'
    assert (await sh.health_check())['healthy'] is True


async def test_sh_token_exchange(sh):
    _sh_get(sh, {'access_token': 't'})
    assert (await sh.exchange_token('code', 'shop.myshopify.com')) == {
        'access_token': 't'}
    resp = _resp({})
    resp.raise_for_status.side_effect = httpx.HTTPError('x')
    sh.http.post = AsyncMock(return_value=resp)
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        await sh.exchange_token('c', 's')


async def test_sh_read_endpoints(sh):
    _sh_get(sh, {'products': [1], 'orders': [2], 'shop': {'name': 'S'},
                 'inventory_levels': [3], 'locations': [4], 'customers': [5],
                 'customer': {'id': 6}, 'fulfillments': [7], 'refunds': [8],
                 'draft_orders': [9], 'transactions': [10]})
    assert await sh.get_products('t', 'my-shop', limit=5) == [1]
    assert await sh.get_orders('t', 'my-shop') == [2]
    assert await sh.get_shop_info('t', 'my-shop') == {'name': 'S'}
    assert await sh.get_inventory_levels('t', 'my-shop', location_id='L') == [3]
    assert await sh.get_locations('t', 'my-shop') == [4]
    assert await sh.get_customers('t', 'my-shop') == [5]
    assert await sh.get_customer('t', 'my-shop', 'c1') == {'id': 6}
    assert await sh.search_customers('t', 'my-shop', 'q') == [5]
    assert await sh.get_fulfillments('t', 'my-shop', 'o1') == [7]
    assert await sh.get_refunds('t', 'my-shop', 'o1') == [8]
    assert await sh.get_draft_orders('t', 'my-shop') == [9]
    assert await sh.get_transactions('t', 'my-shop', 'o1') == [10]


async def test_sh_write_endpoints(sh):
    _sh_get(sh, {'fulfillment': {'id': 'f'}, 'draft_order': {'id': 'd'},
                 'refund': {'id': 'r'}})
    assert await sh.create_fulfillment(
        't', 'my-shop', 'o1', 'loc', tracking_number='TN',
        tracking_company='UPS') == {'id': 'f'}
    assert await sh.create_draft_order(
        't', 'my-shop', [{'x': 1}], customer_id='c') == {'id': 'd'}
    assert await sh.complete_draft_order('t', 'my-shop', 'd1') == {'id': 'd'}
    assert await sh.calculate_refund('t', 'my-shop', 'o1', [{}]) == {'id': 'r'}


async def test_sh_error_branches(sh):
    _sh_get(sh, {}, status=500)
    from fastapi import HTTPException
    for coro in (sh.get_products('t', 's'), sh.get_orders('t', 's'),
                 sh.get_shop_info('t', 's'), sh.get_inventory_levels('t', 's'),
                 sh.get_locations('t', 's'), sh.get_customers('t', 's'),
                 sh.get_customer('t', 's', 'c'), sh.search_customers('t', 's', 'q'),
                 sh.get_fulfillments('t', 's', 'o'), sh.get_refunds('t', 's', 'o'),
                 sh.get_draft_orders('t', 's'),
                 sh.create_draft_order('t', 's', []),
                 sh.complete_draft_order('t', 's', 'd'),
                 sh.get_transactions('t', 's', 'o'),
                 sh.create_fulfillment('t', 's', 'o', 'l'),
                 sh.calculate_refund('t', 's', 'o', []),
                 sh.get_shop_analytics('t', 's')):
        with pytest.raises(HTTPException):
            await coro
    # count endpoints swallow errors
    assert await sh.get_order_count('t', 's') == 0
    assert await sh.get_product_count('t', 's') == 0
    assert await sh.get_customer_count('t', 's') == 0


async def test_sh_counts_and_analytics(sh):
    sh.get_order_count = AsyncMock(return_value=1)
    sh.get_product_count = AsyncMock(return_value=2)
    sh.get_customer_count = AsyncMock(return_value=3)
    sh.get_shop_info = AsyncMock(
        return_value={'name': 'S', 'domain': 'd', 'currency': 'EUR',
                      'plan_name': 'basic', 'created_at': '2026'})
    a = await sh.get_shop_analytics('t', 's')
    assert a['metrics'] == {'total_orders': 1, 'total_products': 2,
                            'total_customers': 3}
    assert a['plan'] == 'basic'
    # count endpoints happy paths via HTTP (fresh service, real methods)
    svc2 = ShopifyService(tenant_id='t2', config={'shop_name': 's'})
    svc2.http = MagicMock()
    _sh_get(svc2, {'count': 7})
    assert await svc2.get_order_count('t', 's') == 7
    assert await svc2.get_product_count('t', 's') == 7
    assert await svc2.get_customer_count('t', 's') == 7


async def test_sh_register_webhooks(sh):
    resp_ok = _resp({'webhook': {'id': 1}})
    resp_422 = _resp({}, status=422)
    resp_err = _resp({}, status=500)
    resp_err.raise_for_status.side_effect = RuntimeError('x')
    sh.http.post = AsyncMock(side_effect=[resp_ok, resp_422, resp_err])
    results = await sh.register_webhooks('t', 'my-shop', 'http://hook')
    assert [r['status'] for r in results] == \
        ['registered', 'already_exists', 'failed']


async def test_sh_handle_webhook_event(sh):
    res = await sh.handle_webhook_event(
        {'customer': {'email': 'a@b.c'}, 'order_number': 5, 'id': 9},
        'orders/create')
    assert res['success'] is True
    assert res['result']['sender_id'] == 'a@b.c'
    assert res['result']['metadata']['order_id'] == 9
    res2 = await sh.handle_webhook_event({}, 'other/topic')
    assert res2 == {'success': True, 'result': None}


async def test_sh_execute_operation(sh):
    sh.get_products = AsyncMock(return_value=[])
    sh.get_orders = AsyncMock(return_value=[])
    sh.get_customers = AsyncMock(return_value=[])
    sh.get_customer = AsyncMock(return_value={})
    sh.search_customers = AsyncMock(return_value=[])
    sh.get_fulfillments = AsyncMock(return_value=[])
    sh.create_fulfillment = AsyncMock(return_value={})
    sh.get_refunds = AsyncMock(return_value=[])
    sh.get_shop_analytics = AsyncMock(return_value={})
    sh.full_sync = AsyncMock(return_value={'success': True})
    sh.handle_webhook_event = AsyncMock(return_value={'success': True})

    assert (await sh.execute_operation('get_products', {'limit': 5}))['success'] is True
    assert (await sh.execute_operation('get_orders', {}))['success'] is True
    assert (await sh.execute_operation('get_customers', {}))['success'] is True
    assert (await sh.execute_operation('get_customer', {'customer_id': 'c'}))['success'] is True
    assert (await sh.execute_operation('search_customers', {'query': 'q'}))['success'] is True
    assert (await sh.execute_operation('get_fulfillments', {'order_id': 'o'}))['success'] is True
    assert (await sh.execute_operation('create_fulfillment',
                                       {'order_id': 'o', 'location_id': 'l'}))['success'] is True
    assert (await sh.execute_operation('get_refunds', {'order_id': 'o'}))['success'] is True
    assert (await sh.execute_operation('get_shop_analytics', {}))['success'] is True
    assert (await sh.execute_operation('full_sync', {'workspace_id': 'w'}))['success'] is True
    assert (await sh.execute_operation(
        'handle_webhook_event', {'payload': {}, 'topic': 't'}))['success'] is True
    assert (await sh.execute_operation('bogus', {}))['success'] is False
    sh.get_products = AsyncMock(side_effect=RuntimeError('x'))
    assert (await sh.execute_operation('get_products', {}))['success'] is False


async def test_sh_sync_to_postgres_cache(sh, monkeypatch):
    res = await sh.sync_to_postgres_cache('w1')
    assert res['success'] is False  # missing token

    sh.config['access_token'] = 'tok'
    sh.get_shop_analytics = AsyncMock(return_value={
        'metrics': {'total_orders': 1, 'total_products': 2,
                    'total_customers': 3}})
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db))
    res = await sh.sync_to_postgres_cache('w1')
    assert res == {'success': True, 'metrics_synced': 3}

    db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    assert (await sh.sync_to_postgres_cache('w1'))['success'] is True

    db.commit = MagicMock(side_effect=RuntimeError('x'))
    assert (await sh.sync_to_postgres_cache('w1'))['success'] is False

    monkeypatch.setattr('core.database.SessionLocal',
                        MagicMock(side_effect=RuntimeError('x')))
    assert (await sh.sync_to_postgres_cache('w1'))['success'] is False


async def test_sh_full_sync(sh):
    sh.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True})
    assert (await sh.full_sync('w1'))['success'] is True
