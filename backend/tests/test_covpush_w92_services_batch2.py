# -*- coding: utf-8 -*-
"""Coverage wave 92 — integrations.salesforce_core_service, zoho_crm_service,
zoho_books_service, monday_service, notion_service, workspace_sync_service.

No network / no LLM: httpx/requests boundaries, DB sessions and platform
integration singletons are all mocked.
"""
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests as requests_mod

import integrations.salesforce_core_service as sfc_mod
from integrations.salesforce_core_service import (
    SalesforceAPIError,
    SalesforceCoreService,
    SalesforceCredentials,
)
import integrations.zoho_crm_service as zc_mod
from integrations.zoho_crm_service import ZohoCRMService
import integrations.zoho_books_service as zb_mod
from integrations.zoho_books_service import ZohoBooksService, get_zoho_books_service
import integrations.monday_service as mon_mod
from integrations.monday_service import MondayService
import integrations.notion_service as nt_mod
from integrations.notion_service import NotionService
import integrations.workspace_sync_service as wss_mod
from integrations.workspace_sync_service import (
    ChangeType,
    SyncConflictResolution,
    WorkspaceSyncService,
)


def _resp(payload=None, status=200, text='body', content=b'x'):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    r.text = text
    r.content = content
    return r


def _creds(**kw):
    base = dict(access_token='tok', instance_url='https://inst.example.com',
                refresh_token='r', expires_at=datetime.now(timezone.utc) +
                timedelta(hours=1), user_id='u1', organization_id='o1',
                username='un')
    base.update(kw)
    return SalesforceCredentials(**base)


# ============================================================================
# SalesforceCoreService
# ============================================================================

class TestSalesforceCoreService:
    def _svc(self, db_pool=None):
        return SalesforceCoreService(db_pool=db_pool)

    def test_init_and_singleton(self):
        svc = self._svc()
        assert svc.db_pool is None
        assert svc.session.headers['User-Agent'] == 'ATOM-Enterprise/1.0'
        assert svc.session.timeout == 30
        # singleton getter
        sfc_mod.salesforce_core_service = None
        s1 = sfc_mod.get_salesforce_core_service()
        s2 = sfc_mod.get_salesforce_core_service()
        assert s1 is s2
        sfc_mod.salesforce_core_service = None

    async def test_get_credentials(self, monkeypatch):
        svc = self._svc()
        fake = types.ModuleType('db_oauth_salesforce')
        good = {
            'access_token': 'a', 'instance_url': 'https://i',
            'refresh_token': 'r',
            'expires_at': (datetime.now(timezone.utc) +
                           timedelta(hours=1)).isoformat(),
            'user_id': 'u', 'organization_id': 'o', 'username': 'n',
        }

        async def tok_found(pool, uid, username=None):
            return dict(good)

        fake.get_user_salesforce_tokens = tok_found
        monkeypatch.setitem(sys.modules, 'db_oauth_salesforce', fake)
        c = await svc.get_credentials('u1')
        assert isinstance(c, SalesforceCredentials) and c.access_token == 'a'

        async def none_tok(pool, uid, username=None):
            return None
        fake.get_user_salesforce_tokens = none_tok
        assert await svc.get_credentials('u1') is None

        expired = dict(good)
        expired['expires_at'] = (datetime.now(timezone.utc) -
                                 timedelta(hours=1)).isoformat()
        fake.get_user_salesforce_tokens = AsyncMock(return_value=expired)
        assert await svc.get_credentials('u1') is None

        async def boom(pool, uid, username=None):
            raise RuntimeError('x')
        fake.get_user_salesforce_tokens = boom
        assert await svc.get_credentials('u1') is None

    def test_make_api_request_ok(self):
        svc = self._svc()
        svc._log_api_usage = MagicMock()
        r = _resp({'records': [1]})
        with patch.object(svc.session, 'request', return_value=r) as m:
            assert svc._make_api_request(_creds(), 'GET',
                                         'query/?q=x') == {'records': [1]}
            assert m.call_args[1]['headers']['Authorization'] == \
                'Bearer tok'
        # endpoint already absolute-path (no version prefix added)
        with patch.object(svc.session, 'request', return_value=r) as m:
            svc._make_api_request(_creds(), 'GET', '/absolute')
            assert m.call_args[1]['url'] == 'https://inst.example.com/absolute'
        # 200 with empty content
        r2 = _resp(None, content=b'')
        with patch.object(svc.session, 'request', return_value=r2):
            assert svc._make_api_request(_creds(), 'GET', 'x') == {}
        # 204
        with patch.object(svc.session, 'request', return_value=_resp(None, 204)):
            assert svc._make_api_request(_creds(), 'DELETE', 'x') == {}

    def test_make_api_request_errors(self):
        svc = self._svc()
        svc._log_api_usage = MagicMock()
        err = _resp({'error': 'bad', 'error_code': 'E1'}, 400)
        with patch.object(svc.session, 'request', return_value=err):
            with pytest.raises(SalesforceAPIError) as ei:
                svc._make_api_request(_creds(), 'GET', 'x')
            assert ei.value.status_code == 400
            assert ei.value.error_code == 'E1'
        # non-json error body
        err2 = _resp(None, 500)
        err2.json.side_effect = ValueError('not json')
        err2.text = 'oops'
        with patch.object(svc.session, 'request', return_value=err2):
            with pytest.raises(SalesforceAPIError) as ei:
                svc._make_api_request(_creds(), 'GET', 'x')
            assert ei.value.error_code == 'HTTP_ERROR'
        # timeout
        with patch.object(svc.session, 'request',
                          side_effect=requests_mod.exceptions.Timeout('t')):
            with pytest.raises(SalesforceAPIError) as ei:
                svc._make_api_request(_creds(), 'GET', 'x')
            assert ei.value.error_code == 'TIMEOUT_ERROR'
        # network error
        with patch.object(svc.session, 'request',
                          side_effect=requests_mod.exceptions.
                          ConnectionError('n')):
            with pytest.raises(SalesforceAPIError) as ei:
                svc._make_api_request(_creds(), 'GET', 'x')
            assert ei.value.error_code == 'NETWORK_ERROR'
        # unexpected error (e.g. bad urljoin input path)
        with patch.object(sfc_mod, 'urljoin', side_effect=RuntimeError('x')):
            with pytest.raises(SalesforceAPIError) as ei:
                svc._make_api_request(_creds(), 'GET', 'x')
            assert ei.value.error_code == 'UNKNOWN_ERROR'

    async def test_log_api_usage(self):
        svc = self._svc(db_pool=MagicMock())
        svc._log_api_usage_async = AsyncMock()
        svc._log_api_usage('u', 'n', 'ep', 5, True, None)
        await asyncio_sleep0()
        assert svc._log_api_usage_async.await_count == 1
        # create_task failure branch
        with patch.object(sfc_mod.asyncio, 'create_task',
                          side_effect=RuntimeError('x')):
            svc._log_api_usage('u', 'n', 'ep', 5, True, None)  # swallowed
        # no db pool -> no-op
        svc2 = self._svc()
        svc2._log_api_usage_async = AsyncMock()
        svc2._log_api_usage('u', 'n', 'ep', 5, True, None)
        assert svc2._log_api_usage_async.await_count == 0

    async def test_log_api_usage_async(self, monkeypatch):
        svc = self._svc(db_pool=MagicMock())
        fake = types.ModuleType('db_oauth_salesforce')
        fake.log_api_usage = AsyncMock()
        monkeypatch.setitem(sys.modules, 'db_oauth_salesforce', fake)
        await svc._log_api_usage_async('u', 'n', 'ep', 1, False, 'err')
        assert fake.log_api_usage.await_count == 1
        # failure swallowed
        fake.log_api_usage = AsyncMock(side_effect=RuntimeError('x'))
        await svc._log_api_usage_async('u', 'n', 'ep', 1, False, 'err')

    async def test_list_accounts(self):
        svc = self._svc()
        with patch.object(svc, 'get_credentials',
                          AsyncMock(return_value=_creds())):
            with patch.object(svc, '_make_api_request',
                              return_value={'records': [{'Id': 1}],
                                            'totalSize': 1, 'done': True}):
                r = await svc.list_accounts('u1', query="Name = 'x'",
                                            fields=['Id', 'Name'],
                                            limit=5, offset=2)
                assert r['ok'] and r['accounts'] == [{'Id': 1}]
                assert r['limit'] == 5
            # api error
            with patch.object(svc, '_make_api_request',
                              side_effect=SalesforceAPIError('boom')):
                r = await svc.list_accounts('u1')
                assert r['ok'] is False and r['error'] == 'api_error'
            # unexpected
            with patch.object(svc, '_make_api_request',
                              side_effect=RuntimeError('x')):
                r = await svc.list_accounts('u1')
                assert r['ok'] is False and r['error'] == 'unexpected_error'
        # auth failure
        with patch.object(svc, 'get_credentials', AsyncMock(return_value=None)):
            r = await svc.list_accounts('u1')
            assert r['ok'] is False and r['error'] == 'authentication_failed'

    async def test_create_account(self):
        svc = self._svc()
        with patch.object(svc, 'get_credentials',
                          AsyncMock(return_value=_creds())):
            with patch.object(svc, '_make_api_request',
                              return_value={'id': 'a1'}):
                r = await svc.create_account('u1',
                                             account_data={'Name': 'A'})
                assert r['ok'] and r['account']['id'] == 'a1'
            # validation error
            r = await svc.create_account('u1', account_data=None)
            assert r['ok'] is False and r['error'] == 'validation_error'
            # api error + unexpected
            with patch.object(svc, '_make_api_request',
                              side_effect=SalesforceAPIError('x')):
                assert (await svc.create_account('u1', account_data={}))['ok'] \
                    is False
            with patch.object(svc, '_make_api_request',
                              side_effect=RuntimeError('x')):
                assert (await svc.create_account('u1', account_data={}))['ok'] \
                    is False
        with patch.object(svc, 'get_credentials', AsyncMock(return_value=None)):
            assert (await svc.create_account('u1',
                                             account_data={}))['ok'] is False

    async def test_list_contacts(self):
        svc = self._svc()
        with patch.object(svc, 'get_credentials',
                          AsyncMock(return_value=_creds())):
            with patch.object(svc, '_make_api_request',
                              return_value={'records': [{'Id': 'c'}]}):
                r = await svc.list_contacts('u1', account_id="acc'1",
                                            query="Email != null")
                assert r['ok'] and r['contacts'] == [{'Id': 'c'}]
                assert "acc''1" in r['query']
            with patch.object(svc, '_make_api_request',
                              side_effect=SalesforceAPIError('x')):
                assert (await svc.list_contacts('u1'))['ok'] is False
            with patch.object(svc, '_make_api_request',
                              side_effect=RuntimeError('x')):
                assert (await svc.list_contacts('u1'))['error'] == \
                    'unexpected_error'
        with patch.object(svc, 'get_credentials', AsyncMock(return_value=None)):
            assert (await svc.list_contacts('u1'))['error'] == \
                'authentication_failed'

    async def test_list_opportunities(self):
        svc = self._svc()
        with patch.object(svc, 'get_credentials',
                          AsyncMock(return_value=_creds())):
            with patch.object(svc, '_make_api_request',
                              return_value={'records': [
                                  {'Amount': 100, 'Probability': 50},
                                  {'Amount': 200, 'Probability': 25}]}):
                r = await svc.list_opportunities('u1', account_id='a',
                                                 stage='Closed')
                assert r['ok']
                stats = r['pipeline_statistics']
                assert stats['total_pipeline_value'] == 300
                assert stats['weighted_pipeline_value'] == 100
            with patch.object(svc, '_make_api_request',
                              side_effect=SalesforceAPIError('x')):
                assert (await svc.list_opportunities('u1'))['ok'] is False
            with patch.object(svc, '_make_api_request',
                              side_effect=RuntimeError('x')):
                assert (await svc.list_opportunities('u1'))['ok'] is False
        with patch.object(svc, 'get_credentials', AsyncMock(return_value=None)):
            assert (await svc.list_opportunities('u1'))['ok'] is False

    async def test_get_user_info(self):
        svc = self._svc()
        with patch.object(svc, 'get_credentials',
                          AsyncMock(return_value=_creds())):
            ok = _resp({'user_id': 'u', 'organization_id': 'o',
                        'username': 'un', 'email': 'e',
                        'display_name': 'd', 'profile_id': 'p',
                        'timezone': 't', 'locale': 'l', 'active': True}, 200)
            with patch.object(sfc_mod.requests, 'get', return_value=ok):
                r = await svc.get_user_info('u1')
                assert r['ok'] and r['user_info']['environment'] == 'sandbox'
            # production instance
            with patch.object(sfc_mod.requests, 'get', return_value=ok):
                with patch.object(svc, 'get_credentials',
                                  AsyncMock(return_value=_creds(
                                      instance_url='https://x.login.'
                                      'salesforce.com'))):
                    r = await svc.get_user_info('u1')
                    assert r['user_info']['environment'] == 'production'
            bad = _resp({}, 403)
            with patch.object(sfc_mod.requests, 'get', return_value=bad):
                r = await svc.get_user_info('u1')
                assert r['ok'] is False and r['error'] == 'user_info_failed'
            with patch.object(sfc_mod.requests, 'get',
                              side_effect=RuntimeError('x')):
                r = await svc.get_user_info('u1')
                assert r['error'] == 'unexpected_error'
        with patch.object(svc, 'get_credentials', AsyncMock(return_value=None)):
            assert (await svc.get_user_info('u1'))['ok'] is False


async def asyncio_sleep0():
    import asyncio
    await asyncio.sleep(0)


# ============================================================================
# ZohoCRMService
# ============================================================================

class TestZohoCRMService:
    @pytest.fixture()
    def svc(self):
        return ZohoCRMService(tenant_id='t1', config={'access_token': 'tok'})

    def _token_record(self, expires_at=None, refresh_token='r',
                      access_token='enc'):
        return SimpleNamespace(expires_at=expires_at,
                               refresh_token=refresh_token,
                               access_token=access_token)

    def _db(self, record):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = record
        return db

    def test_init_caps_health(self, svc, monkeypatch):
        monkeypatch.delenv('ZOHO_CRM_ACCESS_TOKEN', raising=False)
        s2 = ZohoCRMService(tenant_id='t2', config={})
        assert s2.access_token is None
        assert svc.base_url.endswith('/crm/v2')
        caps = svc.get_capabilities()
        assert 'get_leads' in caps['operations']
        assert svc.health_check()['healthy'] is True
        assert s2.health_check()['healthy'] is False

    async def test_execute_operation(self, svc):
        svc.get_leads = AsyncMock(return_value=[1])
        svc.get_deals = AsyncMock(return_value=[2])
        svc.get_modules = AsyncMock(return_value=[3])
        svc.create_lead = AsyncMock(return_value={})
        svc.create_record = AsyncMock(return_value={})
        for op, params in (('get_leads', {}), ('get_deals', {}),
                           ('get_modules', {}), ('create_lead', {'a': 1}),
                           ('create_record', {'a': 1})):
            r = await svc.execute_operation(op, params)
            assert r['success'] is True, op
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_leads = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('get_leads', {}))['success'] is \
            False

    async def test_get_active_token_no_tenant(self, svc, monkeypatch):
        monkeypatch.setenv('ZOHO_CRM_ACCESS_TOKEN', 'envtok')
        bare = ZohoCRMService(tenant_id='', config={})
        assert await bare._get_active_token() == 'envtok'
        assert await bare._get_active_token(None) == 'envtok'

    async def test_get_active_token_db_branches(self, svc, monkeypatch):
        # no record
        db = self._db(None)
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        assert await svc._get_active_token('t1') is None
        assert db.close.called

        # valid token -> decrypt
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        db = self._db(self._token_record(expires_at=future))
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        with patch('core.privsec.token_encryption.decrypt_token',
                   return_value='plain') as d:
            assert await svc._get_active_token('t1') == 'plain'
            assert d.called

        # naive expires_at normalized
        db = self._db(self._token_record(
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None) +
            timedelta(hours=1)))
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        with patch('core.privsec.token_encryption.decrypt_token',
                   return_value='plain'):
            assert await svc._get_active_token('t1') == 'plain'

        # expired with refresh token -> refresh succeeds
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        rec = self._token_record(expires_at=past, refresh_token='enc_r')
        db = self._db(rec)
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        with patch('core.privsec.token_encryption.decrypt_token',
                   return_value='r'), \
             patch('core.privsec.token_encryption.encrypt_token',
                   return_value='enc2'), \
             patch('core.privsec.token_encryption.'
                   'stamp_credential_metadata') as stamp, \
             patch.object(svc, 'refresh_token',
                          AsyncMock(return_value={'access_token': 'n',
                                                  'expires_in': 3600})):
            assert await svc._get_active_token('t1') == 'enc2'
            assert stamp.called and db.commit.called

        # refresh fails -> None
        db = self._db(self._token_record(expires_at=past))
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        with patch.object(svc, 'refresh_token', AsyncMock(return_value=None)):
            assert await svc._get_active_token('t1') is None

        # expired without refresh token -> None
        db = self._db(self._token_record(expires_at=past, refresh_token=None))
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        assert await svc._get_active_token('t1') is None

        # no expires_at -> treated expired path with refresh
        db = self._db(self._token_record(expires_at=None))
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        with patch.object(svc, 'refresh_token', AsyncMock(return_value=None)):
            assert await svc._get_active_token('t1') is None

        # exception branch
        db = MagicMock()
        db.query.side_effect = RuntimeError('x')
        monkeypatch.setattr(zc_mod, 'SessionLocal', MagicMock(return_value=db))
        assert await svc._get_active_token('t1') is None

    async def test_refresh_token(self, svc, monkeypatch):
        monkeypatch.delenv('ZOHO_CRM_CLIENT_ID', raising=False)
        monkeypatch.delenv('ZOHO_CRM_CLIENT_SECRET', raising=False)
        assert await svc.refresh_token('r') is None
        monkeypatch.setenv('ZOHO_CRM_CLIENT_ID', 'cid')
        monkeypatch.setenv('ZOHO_CRM_CLIENT_SECRET', 'sec')
        with patch.object(svc, 'client', MagicMock()) as cl:
            cl.post = AsyncMock(return_value=_resp({'access_token': 'n'}))
            assert (await svc.refresh_token('r'))['access_token'] == 'n'
            cl.post = AsyncMock(side_effect=RuntimeError('x'))
            assert await svc.refresh_token('r') is None

    async def test_get_leads_and_deals(self, svc):
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value=None)):
            with pytest.raises(Exception):
                await svc.get_leads()
            with pytest.raises(Exception):
                await svc.get_deals()
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value='tok')):
            with patch.object(svc, 'client', MagicMock()) as cl:
                cl.get = AsyncMock(return_value=_resp({'data': [{'id': 1}]}))
                assert await svc.get_leads() == [{'id': 1}]
                assert await svc.get_deals() == [{'id': 1}]
                bad = _resp({}, 500)
                bad.raise_for_status.side_effect = requests_mod.HTTPError('x')
                cl.get = AsyncMock(return_value=bad)
                assert await svc.get_leads() == []
                assert await svc.get_deals() == []
                cl.get = AsyncMock(side_effect=RuntimeError('x'))
                assert await svc.get_leads() == []

    async def test_create_lead_and_record(self, svc):
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value=None)):
            with pytest.raises(Exception):
                await svc.create_lead({'a': 1})
            with pytest.raises(Exception):
                await svc.create_record('Leads', {'a': 1})
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value='tok')):
            with patch.object(svc, 'client', MagicMock()) as cl:
                cl.post = AsyncMock(return_value=_resp({'data': [{'id': 'x'}]}))
                assert await svc.create_lead({'a': 1}) == {'id': 'x'}
                assert await svc.create_record('Deals', {'a': 1}) == {'id': 'x'}
                cl.post = AsyncMock(side_effect=RuntimeError('x'))
                with pytest.raises(Exception):
                    await svc.create_lead({'a': 1})
                with pytest.raises(Exception):
                    await svc.create_record('Leads', {})

    async def test_get_modules_and_fields(self, svc):
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value=None)):
            assert await svc.get_modules() == []
            assert await svc.get_fields('Leads') == []
        with patch.object(svc, '_get_active_token',
                          AsyncMock(return_value='tok')):
            with patch.object(svc, 'client', MagicMock()) as cl:
                cl.get = AsyncMock(side_effect=[
                    _resp({'modules': [{'api_name': 'Leads'}]}),
                    _resp({'fields': [{'id': 'f'}]}),
                    RuntimeError('x'), RuntimeError('x')])
                assert await svc.get_modules() == [{'api_name': 'Leads'}]
                assert await svc.get_fields('Leads') == [{'id': 'f'}]
                assert await svc.get_modules() == []
                assert await svc.get_fields('Leads') == []

    async def test_sync_to_postgres_cache(self, svc, monkeypatch):
        svc.get_leads = AsyncMock(return_value=[{}, {}])
        svc.get_deals = AsyncMock(
            return_value=[{'Amount': 10}, {'Amount': '30'}])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('ws1')
        assert r == {'success': True, 'metrics_synced': 3}
        # existing metric rows updated
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await svc.sync_to_postgres_cache('ws1'))['metrics_synced'] == 3
        # commit error
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws1'))['success'] is False
        # outer exception
        svc.get_leads = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws1'))['success'] is False

    async def test_full_sync(self, svc):
        svc.sync_to_postgres_cache = AsyncMock(
            return_value={'success': True, 'metrics_synced': 3})
        r = await svc.full_sync('ws1')
        assert r['success'] and r['workspace_id'] == 'ws1'


# ============================================================================
# ZohoBooksService
# ============================================================================

class TestZohoBooksService:
    @pytest.fixture()
    def svc(self):
        return ZohoBooksService(tenant_id='t1',
                                config={'client_id': 'cid',
                                        'client_secret': 'sec',
                                        'access_token': 'tok'})

    def test_init_caps_health(self):
        s = ZohoBooksService(tenant_id='t', config={})
        assert s.client_id is None or isinstance(s.client_id, str)
        assert s.base_url.endswith('/books/v3')
        assert svc_caps(s)['supports_webhooks'] is False
        assert s.health_check()['healthy'] is False
        assert get_zoho_books_service({'access_token': 'a'}) \
            .access_token == 'a'
        assert isinstance(zb_mod.zoho_books_service, ZohoBooksService)

    async def test_execute_operation(self, svc):
        svc.get_organizations = AsyncMock(return_value=[{'id': 1}])
        svc.get_contacts = AsyncMock(return_value=[{'id': 2}])
        r = await svc.execute_operation('get_organizations',
                                        {'access_token': 'a'})
        assert r['success'] and r['result'] == [{'id': 1}]
        r = await svc.execute_operation(
            'get_contacts', {'access_token': 'a', 'organization_id': 'o'})
        assert r['success'] and r['result'] == [{'id': 2}]
        # uses self.access_token when not in params
        await svc.execute_operation('get_organizations', {})
        assert svc.get_organizations.await_args[0][0] == 'tok'
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_organizations = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('get_organizations',
                                            {}))['success'] is False

    async def test_get_active_token_no_tenant(self, monkeypatch):
        monkeypatch.delenv('ZOHO_BOOKS_ACCESS_TOKEN', raising=False)
        bare = ZohoBooksService(tenant_id='', config={})
        assert await bare._get_active_token() is None
        monkeypatch.setenv('ZOHO_BOOKS_ACCESS_TOKEN', 'envt')
        assert await bare._get_active_token() == 'envt'

    async def test_get_active_token_db_branches(self, svc, monkeypatch):
        def rec(expires_at, refresh_token='r', access_token='enc'):
            return SimpleNamespace(expires_at=expires_at,
                                   refresh_token=refresh_token,
                                   access_token=access_token)

        def db_with(record):
            db = MagicMock()
            db.query.return_value.filter.return_value.first.return_value = \
                record
            return db

        db = db_with(None)
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert await svc._get_active_token('t1') is None

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        db = db_with(rec(future))
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        with patch('core.privsec.token_encryption.decrypt_token',
                   return_value='plain'):
            assert await svc._get_active_token('t1') == 'plain'

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        db = db_with(rec(past))
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        with patch('core.privsec.token_encryption.decrypt_token',
                   return_value='r'), \
             patch('core.privsec.token_encryption.encrypt_token',
                   return_value='enc2'), \
             patch.object(svc, 'refresh_token',
                          AsyncMock(return_value={'access_token': 'n'})):
            assert await svc._get_active_token('t1') == 'enc2'
        # fresh expired record: refresh returns None -> None
        db = db_with(rec(past))
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        with patch.object(svc, 'refresh_token', AsyncMock(return_value=None)):
            assert await svc._get_active_token('t1') is None
        # fresh expired record without refresh token -> None
        db = db_with(rec(past, refresh_token=None))
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert await svc._get_active_token('t1') is None
        # session_id fallback + exception branch
        svc.session_id = 'sid'
        db = MagicMock()
        db.query.side_effect = RuntimeError('x')
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        assert await svc._get_active_token() is None

    async def test_refresh_and_exchange(self, svc):
        with patch.object(svc, 'client', MagicMock()) as cl:
            cl.post = AsyncMock(return_value=_resp({'access_token': 'n'}))
            assert (await svc.refresh_token('r'))['access_token'] == 'n'
            assert (await svc.exchange_token('c', 'http://cb'))['access_token'] \
                == 'n'
            cl.post = AsyncMock(side_effect=RuntimeError('x'))
            assert await svc.refresh_token('r') is None
            with pytest.raises(Exception):
                await svc.exchange_token('c', 'http://cb')

    def test_get_headers(self, svc):
        h = svc._get_headers('t', 'o')
        assert h['Authorization'] == 'Zoho-oauthtoken t'

    async def test_getters(self, svc):
        with patch.object(svc, 'client', MagicMock()) as cl:
            cl.get = AsyncMock(side_effect=[
                _resp({'organizations': [{'id': 1}]}),
                _resp({'chartofaccounts': [{'id': 2}]}),
                _resp({'banktransactions': [{'id': 3}]}),
                _resp({'contacts': [{'id': 4}]}),
                RuntimeError('x'), RuntimeError('x'),
                RuntimeError('x'), RuntimeError('x')])
            assert await svc.get_organizations('a') == [{'id': 1}]
            assert await svc.get_chart_of_accounts('a', 'o') == [{'id': 2}]
            assert await svc.get_bank_transactions('a', 'o', 'acc') == \
                [{'id': 3}]
            assert await svc.get_contacts('a', 'o') == [{'id': 4}]
            assert await svc.get_organizations('a') == []
            assert await svc.get_chart_of_accounts('a', 'o') == []
            assert await svc.get_bank_transactions('a', 'o', 'acc') == []
            assert await svc.get_contacts('a', 'o') == []

    async def test_creates(self, svc):
        with patch.object(svc, 'client', MagicMock()) as cl:
            cl.post = AsyncMock(return_value=_resp({'contact': {'id': 'c'},
                                                    'invoice': {'id': 'i'}}))
            assert await svc.create_contact('a', 'o', {}) == {'id': 'c'}
            assert await svc.create_invoice('a', 'o', {}) == {'id': 'i'}
            cl.post = AsyncMock(side_effect=RuntimeError('x'))
            with pytest.raises(Exception):
                await svc.create_contact('a', 'o', {})
            with pytest.raises(Exception):
                await svc.create_invoice('a', 'o', {})

    async def test_sync_to_postgres_cache(self, svc, monkeypatch):
        svc.get_chart_of_accounts = AsyncMock(return_value=[
            {'account_id': 'b1', 'account_type': 'bank'},
            {'account_id': 'x', 'account_type': 'other'}])
        svc.get_bank_transactions = AsyncMock(return_value=[{}, {}])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('u1', 'a', 'o')
        assert r == {'success': True, 'metrics_synced': 2}
        # no bank account -> tx_count 0
        svc.get_chart_of_accounts = AsyncMock(return_value=[{'x': 1}])
        assert (await svc.sync_to_postgres_cache('u1', 'a', 'o'))[
            'metrics_synced'] == 2
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('u1', 'a', 'o'))[
            'success'] is False
        svc.get_chart_of_accounts = AsyncMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('u1', 'a', 'o'))[
            'success'] is False

    async def test_full_sync(self, svc):
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('u1', 'a', 'o')
        assert r['success'] and r['user_id'] == 'u1'


def svc_caps(s):
    return s.get_capabilities()


# ============================================================================
# MondayService
# ============================================================================

class TestMondayService:
    @pytest.fixture()
    def svc(self):
        return MondayService(tenant_id='t1', config={'client_id': 'cid',
                                                     'client_secret': 'sec'})

    def test_init_and_auth_url(self, svc, monkeypatch):
        for v in ('MONDAY_CLIENT_ID', 'MONDAY_CLIENT_SECRET'):
            monkeypatch.delenv(v, raising=False)
        s2 = MondayService(tenant_id='t2', config={})
        assert s2.client_id is None
        url = svc.get_authorization_url('st1')
        assert 'state=st1' in url and 'client_id=cid' in url
        assert svc.get_authorization_url().endswith('state=no_workspace')

    def test_exchange_and_refresh(self, svc):
        payload = {'access_token': 'a', 'refresh_token': 'r',
                   'expires_in': 1, 'token_type': 'bearer', 'scope': 's'}
        with patch.object(mon_mod.requests, 'post',
                          return_value=_resp(payload)):
            r = svc.exchange_code_for_token('code')
            assert r['access_token'] == 'a'
            assert svc.refresh_access_token('r') == payload
        bad = _resp({}, 500)
        bad.raise_for_status.side_effect = requests_mod.HTTPError('x')
        with patch.object(mon_mod.requests, 'post', return_value=bad):
            with pytest.raises(requests_mod.RequestException):
                svc.exchange_code_for_token('c')
            with pytest.raises(requests_mod.RequestException):
                svc.refresh_access_token('r')

    def test_make_request(self, svc):
        with patch.object(mon_mod.requests, 'post',
                          return_value=_resp({'data': 1})):
            assert svc._make_request('t', 'q', {'v': 1}) == {'data': 1}
        bad = _resp({}, 500)
        bad.raise_for_status.side_effect = requests_mod.HTTPError('x')
        with patch.object(mon_mod.requests, 'post', return_value=bad):
            with pytest.raises(requests_mod.RequestException):
                svc._make_request('t', 'q')

    def test_graphql_wrappers(self, svc):
        svc._make_request = MagicMock(return_value={
            'data': {'boards': [{'id': 'b'}],
                     'create_item': {'id': 'i'},
                     'change_multiple_column_values': {'id': 'i2'},
                     'workspaces': [{'id': 'w'}],
                     'users': [{'id': 'u'}],
                     'create_board': {'id': 'nb'},
                     'items': [{'id': 'it'}]}})
        assert svc.get_boards('t', 'w1') == [{'id': 'b'}]
        assert svc.get_board('t', 'b1') == {'id': 'b'}
        assert svc.get_items('t', 'b1') is not None
        assert svc.create_item('t', 'b1', 'N', {'c': 1}) == {'id': 'i'}
        assert svc.update_item('t', 'i1', {'c': 2}) == {'id': 'i2'}
        assert svc.update_item('t', 'i1') == {'id': 'i2'}
        assert svc.get_workspaces('t') == [{'id': 'w'}]
        assert svc.get_users('t', 'w1') == [{'id': 'u'}]
        assert svc.get_users('t') == [{'id': 'u'}]
        assert svc.create_board('t', 'N', workspace_id='w',
                                template_id='tp') == {'id': 'nb'}
        assert svc.search_items('t', 'q', ['b1']) == [{'id': 'it'}]
        assert svc.search_items('t', 'q') == [{'id': 'it'}]
        # empty results
        svc._make_request = MagicMock(return_value={'data': {}})
        assert svc.get_board('t', 'b') == {}
        assert svc.get_items('t', 'b') == []

    def test_health_status(self, svc):
        svc._make_request = MagicMock(return_value={'data': {'boards': []}})
        h = svc.get_health_status('t')
        assert h['status'] == 'healthy'
        svc._make_request = MagicMock(return_value={})
        assert svc.get_health_status('t')['status'] == 'unhealthy'
        svc._make_request = MagicMock(side_effect=RuntimeError('x'))
        assert svc.get_health_status('t')['status'] == 'error'

    async def test_execute_operation(self, svc):
        svc.get_boards = MagicMock(return_value=[1])
        svc.get_board = MagicMock(return_value={2: 'b'})
        svc.get_items = MagicMock(return_value=[3])
        svc.create_item = MagicMock(return_value={4: 'i'})
        svc.update_item = MagicMock(return_value={5: 'i'})
        svc.get_workspaces = MagicMock(return_value=[6])
        svc.get_users = MagicMock(return_value=[7])
        svc.create_board = MagicMock(return_value={8: 'b'})
        svc.search_items = MagicMock(return_value=[9])
        params = {'access_token': 't', 'board_id': 'b', 'item_name': 'n',
                  'item_id': 'i', 'name': 'N', 'query_term': 'q'}
        for op in ('get_boards', 'get_board', 'get_items', 'create_item',
                   'update_item', 'get_workspaces', 'get_users',
                   'create_board', 'search_items'):
            r = await svc.execute_operation(op, dict(params))
            assert r['success'] is True, op
        assert (await svc.execute_operation('nope', {}))['success'] is False
        svc.get_boards = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('get_boards', {}))['success'] is \
            False

    async def test_sync_to_postgres_cache(self, svc, monkeypatch):
        svc.get_boards = MagicMock(return_value=[{'items_count': 3}])
        svc.get_users = MagicMock(return_value=[{}, {}])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('t', 'ws1')
        assert r == {'success': True, 'metrics_synced': 3}
        # missing workspace id
        assert (await svc.sync_to_postgres_cache('t'))['success'] is False
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('t', 'ws1'))['success'] is \
            False
        svc.get_boards = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('t', 'ws1'))['success'] is \
            False

    async def test_full_sync_caps_health(self, svc):
        svc.sync_to_postgres_cache = AsyncMock(return_value={'success': True})
        r = await svc.full_sync('t', 'ws1')
        assert r['success'] and r['workspace_id'] == 'ws1'
        assert svc.get_capabilities()['supports_webhooks'] is True
        assert svc.health_check()['healthy'] is True


# ============================================================================
# NotionService
# ============================================================================

class TestNotionService:
    @pytest.fixture()
    def svc(self):
        return NotionService(tenant_id='t1',
                             config={'access_token': 'tok'})

    def test_init(self, svc):
        s = NotionService(tenant_id='t2', config={})
        assert s.access_token is None
        assert 'Bearer tok' in svc.session.headers.get('Authorization', '')

    def test_capabilities(self, svc):
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is False
        assert {o['id'] for o in caps['operations']} >= \
            {'read', 'create', 'search'}

    async def test_health_check(self, svc):
        assert (await svc.health_check())['healthy'] is True

    async def test_execute_operation(self, svc):
        svc.search = MagicMock(return_value={'results': [1]})
        r = await svc.execute_operation('search', {'query': 'q'})
        assert r['success'] and r['result'] == {'results': [1]}
        svc.get_page = MagicMock(return_value={'id': 'p'})
        r = await svc.execute_operation('get_page', {'page_id': 'p'})
        assert r['success']
        svc.create_page = MagicMock(return_value={'id': 'np'})
        r = await svc.execute_operation(
            'create_page', {'parent': {'page_id': 'x'},
                            'properties': {}})
        assert r['success']
        assert (await svc.execute_operation('nope', {}))['success'] is False
        # tenant mismatch
        r = await svc.execute_operation(
            'search', {}, context={'tenant_id': 'other'})
        assert r['success'] is False and 'mismatch' in r['error']
        # matching tenant context ok
        r = await svc.execute_operation('search', {},
                                        context={'tenant_id': 't1'})
        assert r['success'] is True
        # exception
        svc.search = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.execute_operation('search', {}))['success'] is False

    def test_connection(self, svc):
        svc.session = MagicMock()
        svc.session.post.return_value = _resp({'results': [1, 2]}, 200)
        r = svc.test_connection()
        assert r['status'] == 'success' and r['results_found'] == 2
        svc.session.post.return_value = _resp({}, 401)
        assert svc.test_connection()['authenticated'] is False
        svc.session.post.side_effect = RuntimeError('x')
        assert svc.test_connection()['status'] == 'error'

    def test_search_and_get(self, svc):
        svc.session = MagicMock()
        svc.session.post.return_value = _resp({'results': [1]})
        assert svc.search('q', {'property': 'object'}, 10) == {'results': [1]}
        assert svc.search() == {'results': [1]}
        svc.session.get.return_value = _resp({'id': 'p'})
        assert svc.get_page('p') == {'id': 'p'}
        assert svc.get_database('d') == {'id': 'p'}
        assert svc.get_user('u') == {'id': 'p'}
        assert svc.get_me() == {'id': 'p'}
        # error branches
        svc.session.post.side_effect = RuntimeError('x')
        assert svc.search() == {'results': [], 'has_more': False}
        svc.session.get.side_effect = RuntimeError('x')
        assert svc.get_page('p') is None
        assert svc.get_database('d') is None
        assert svc.get_user('u') is None

    def test_page_crud(self, svc):
        svc.session = MagicMock()
        svc.session.post.return_value = _resp({'id': 'np'})
        assert svc.create_page({'page_id': 'x'}, {}, [{'b': 1}]) == \
            {'id': 'np'}
        # invalid parent
        assert svc.create_page({}, {}) is None
        assert svc.create_page({'foo': 1}, {}) is None
        svc.session.patch.return_value = _resp({'id': 'up'})
        assert svc.update_page('p', {}, archived=True) == {'id': 'up'}
        svc.session.post.side_effect = RuntimeError('x')
        assert svc.create_page({'page_id': 'x'}, {}) is None
        svc.session.patch.side_effect = RuntimeError('x')
        assert svc.update_page('p', {}) is None

    def test_database_ops(self, svc):
        svc.session = MagicMock()
        svc.session.post.return_value = _resp({'results': [1]})
        assert svc.query_database('d', {'f': 1}, [{'s': 1}], 'cur',
                                  5) == {'results': [1]}
        assert svc.create_database({'page_id': 'x'}, 'T', {}) == \
            {'results': [1]}
        svc.session.post.side_effect = RuntimeError('x')
        assert svc.query_database('d') == {'results': [], 'has_more': False}
        assert svc.create_database({'page_id': 'x'}, 'T', {}) is None

    def test_block_ops(self, svc):
        svc.session = MagicMock()
        svc.session.get.return_value = _resp({'results': [1]})
        assert svc.get_block_children('b', 10) == {'results': [1]}
        svc.session.patch.return_value = _resp({'ok': 1})
        assert svc.append_block_children('b', [{'x': 1}]) == {'ok': 1}
        assert svc.delete_block('b') is True
        svc.session.get.side_effect = RuntimeError('x')
        assert svc.get_block_children('b') == {'results': [],
                                               'has_more': False}
        svc.session.patch.side_effect = RuntimeError('x')
        assert svc.append_block_children('b', []) is None
        assert svc.delete_block('b') is False

    def test_block_factories(self, svc):
        b = svc.create_text_block('hi', {'bold': True})
        assert b['type'] == 'paragraph'
        h = svc.create_heading_block('hi', 2)
        assert h['type'] == 'heading_2'
        t = svc.create_todo_block('todo', True)
        assert t['to_do']['checked'] is True
        rt = svc.format_text_rich_text('x', bold=True, color='red')
        assert rt['annotations']['color'] == 'red'

    def test_helpers(self, svc):
        svc.create_page = MagicMock(return_value={'id': 'p'})
        props = {'Other': {}}
        assert svc.create_page_in_database('db1', props,
                                           content_blocks=[{'b': 1}]) == \
            {'id': 'p'}
        parent = svc.create_page.call_args[0][0]
        assert parent['database_id'] == 'db1'
        assert 'Name' in props
        # create_page raising -> caught
        svc.create_page = MagicMock(side_effect=RuntimeError('x'))
        assert svc.create_page_in_database('db1', {}) is None
        svc.search = MagicMock(return_value={'results': [{'id': 1}]})
        assert svc.search_pages_in_workspace('q') == [{'id': 1}]
        assert svc.search_databases_in_workspace('q') == [{'id': 1}]
        svc.search = MagicMock(side_effect=RuntimeError('x'))
        assert svc.search_pages_in_workspace() == []
        assert svc.search_databases_in_workspace() == []

    async def test_sync_and_full_sync(self, svc, monkeypatch):
        svc.search_pages_in_workspace = MagicMock(return_value=[{'id': 1}])
        svc.search_databases_in_workspace = MagicMock(return_value=[{}, {}])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await svc.sync_to_postgres_cache('ws1')
        assert r == {'success': True, 'metrics_synced': 2}
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws1'))['success'] is False
        svc.search_pages_in_workspace = MagicMock(
            side_effect=RuntimeError('x'))
        assert (await svc.sync_to_postgres_cache('ws1'))['success'] is False
        svc.sync_to_postgres_cache = AsyncMock(
            return_value={'success': True})
        r = await svc.full_sync()
        assert r['success'] and r['workspace_id'] == 'default'


def svc_session_auth(fix):
    svc = NotionService(tenant_id='t1', config={'access_token': 'tok2'})
    return svc.session.headers.get('Authorization', '')


# ============================================================================
# WorkspaceSyncService
# ============================================================================

def _ws(**kw):
    base = dict(id='ws1', user_id='u1', name='WS', description=None,
                slack_workspace_id=None, discord_guild_id=None,
                google_chat_space_id=None, teams_team_id=None,
                platform_count=0, sync_status='active', last_sync_at=None,
                sync_config={})
    base.update(kw)
    return SimpleNamespace(**base)


def _log(**kw):
    base = dict(operation='propagate', source_platform='slack',
                target_platforms=['discord'], change_type='name_change',
                status='success', started_at=datetime(2026, 1, 1, 10, 0, 0),
                duration_ms=None)
    base.update(kw)
    return SimpleNamespace(**base)


class TestWorkspaceSyncService:
    @pytest.fixture()
    def svc(self):
        return WorkspaceSyncService(db=MagicMock())

    def test_capabilities_and_health(self, svc):
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is False
        assert {o['id'] for o in caps['operations']} >= \
            {'sync_workspace', 'list_syncs'}
        assert svc.health_check()['healthy'] is True
        svc.db.execute.side_effect = RuntimeError('x')
        h = svc.health_check()
        assert h['healthy'] is False and h['error'] == 'Database connection failed'
        assert WorkspaceSyncService(db=None).health_check()['healthy'] is \
            False

    def test_platform_id_helpers(self):
        ws = _ws(slack_workspace_id='T1')
        assert WorkspaceSyncService._get_platform_id(ws, 'slack') == 'T1'
        assert WorkspaceSyncService._get_platform_id(ws, 'bogus') is None
        WorkspaceSyncService._set_platform_id(ws, 'teams', 'tm1')
        assert ws.teams_team_id == 'tm1'
        with pytest.raises(ValueError):
            WorkspaceSyncService._set_platform_id(ws, 'bogus', 'x')

    def test_create_unified_workspace(self, svc):
        ws = svc.create_unified_workspace(
            'u1', 'WS', description='d', slack_workspace_id='T1',
            discord_guild_id='G1', sync_config={'auto_sync': False})
        assert ws.platform_count == 2
        assert svc.db.add.called and svc.db.commit.called
        assert svc.db.refresh.called
        # default sync config
        ws2 = svc.create_unified_workspace('u1', 'W2')
        assert isinstance(ws2, type(ws))
        # failure -> rollback + raise
        svc.db.commit.side_effect = RuntimeError('x')
        with pytest.raises(RuntimeError):
            svc.create_unified_workspace('u1', 'W3')
        assert svc.db.rollback.called

    def test_add_platform(self, svc):
        ws = _ws(slack_workspace_id='T1')
        svc.db.query.return_value.filter.return_value.first.return_value = ws
        out = svc.add_platform_to_workspace('ws1', 'discord', 'G1')
        assert out.discord_guild_id == 'G1' and out.platform_count == 2
        # platform already present (warning path, still succeeds)
        svc.add_platform_to_workspace('ws1', 'slack', 'T2')
        assert ws.slack_workspace_id == 'T2'
        # not found
        svc.db.query.return_value.filter.return_value.first.return_value = \
            None
        with pytest.raises(ValueError):
            svc.add_platform_to_workspace('nope', 'slack', 'T')
        # error -> rollback
        svc.db.query.return_value.filter.return_value.first.return_value = ws
        svc.db.commit.side_effect = RuntimeError('x')
        with pytest.raises(RuntimeError):
            svc.add_platform_to_workspace('ws1', 'teams', 't')

    def test_log_and_update_sync_log(self, svc):
        lid = svc._log_sync_operation(
            'ws1', 'propagate', 'slack', ['discord'], 'name_change',
            {'new_name': 'N'}, 'in_progress')
        assert svc.db.flush.called
        assert lid is None or isinstance(lid, object)
        log = _log()
        svc.db.query.return_value.filter.return_value.first.return_value = log
        svc._update_sync_log('log1', 'success',
                             completed_at=datetime(2026, 1, 1, 10, 0, 1,
                                                   tzinfo=timezone.utc))
        assert log.status == 'success' and log.duration_ms == 1000
        # naive completed_at
        log2 = _log()
        svc.db.query.return_value.filter.return_value.first.return_value = \
            log2
        svc._update_sync_log('log1', 'failure',
                             completed_at=datetime(2026, 1, 1, 10, 0, 2),
                             error_message='2 failed')
        assert log2.error_message == '2 failed'
        # missing log / no started_at
        svc.db.query.return_value.filter.return_value.first.return_value = \
            None
        svc._update_sync_log('gone', 'success', completed_at=None)
        log3 = _log(started_at=None)
        svc.db.query.return_value.filter.return_value.first.return_value = \
            log3
        svc._update_sync_log('log1', 'success',
                             completed_at=datetime(2026, 1, 1,
                                                   tzinfo=timezone.utc))

    def test_propagate_change(self, svc):
        ws = _ws(slack_workspace_id='T1', discord_guild_id='G1',
                 teams_team_id='TM1')
        svc.db.query.return_value.filter.return_value.first.return_value = ws
        svc._log_sync_operation = MagicMock(return_value='log1')
        svc._update_sync_log = MagicMock()
        # all targets succeed
        svc._apply_change_to_platform = MagicMock(
            return_value={'success': True})
        r = svc.propagate_change('ws1', 'slack', 'name_change',
                                 {'new_name': 'N'})
        assert r['status'] == 'success'
        assert r['successful_platforms'] == ['discord', 'teams']
        # partial failure
        svc._apply_change_to_platform = MagicMock(
            side_effect=lambda **kw: {'success': kw['target_platform'] ==
                                      'discord'})
        r = svc.propagate_change('ws1', 'slack', 'name_change', {})
        assert r['status'] == 'partial_failure'
        # total failure
        svc._apply_change_to_platform = MagicMock(
            return_value={'success': False})
        r = svc.propagate_change('ws1', 'slack', 'name_change', {})
        assert r['status'] == 'failure' and ws.sync_status == 'error'
        # exception inside per-target apply
        svc._apply_change_to_platform = MagicMock(side_effect=RuntimeError('x'))
        r = svc.propagate_change('ws1', 'slack', 'name_change', {})
        assert r['failed_platforms'] == ['discord', 'teams']
        # no targets
        solo = _ws(slack_workspace_id='T1')
        svc.db.query.return_value.filter.return_value.first.return_value = \
            solo
        assert svc.propagate_change('ws1', 'slack', 'x', {}) == \
            {'status': 'no_targets', 'targets': []}
        # workspace missing -> raise + rollback
        svc.db.query.return_value.filter.return_value.first.return_value = \
            None
        with pytest.raises(ValueError):
            svc.propagate_change('nope', 'slack', 'x', {})
        assert svc.db.rollback.called

    def test_get_workspace_sync_status(self, svc):
        ws = _ws(slack_workspace_id='T1', discord_guild_id='G1',
                 platform_count=2,
                 last_sync_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        logs = [_log(), _log(operation='create', status='success')]
        ws_q = MagicMock()
        ws_q.filter.return_value.first.return_value = ws
        log_q = MagicMock()
        log_q.filter.return_value.order_by.return_value.limit.\
            return_value.all.return_value = logs
        svc.db.query.side_effect = lambda cls: \
            ws_q if cls is wss_mod.UnifiedWorkspace else log_q
        st = svc.get_workspace_sync_status('ws1')
        assert st['name'] == 'WS' and st['platform_count'] == 2
        assert len(st['recent_syncs']) == 2
        assert st['recent_syncs'][0]['started_at'].startswith('2026')
        # not found
        ws_q.filter.return_value.first.return_value = None
        with pytest.raises(ValueError):
            svc.get_workspace_sync_status('nope')

    def test_connected_platforms_and_routing(self, svc):
        ws = _ws(slack_workspace_id='T1', discord_guild_id='G1',
                 google_chat_space_id='S1', teams_team_id='TM1')
        assert svc._get_connected_platforms(ws) == \
            ['slack', 'discord', 'google_chat', 'teams']
        assert svc._get_connected_platforms(ws, exclude='discord') == \
            ['slack', 'google_chat', 'teams']
        # routing
        for platform, meth in (('slack', '_apply_slack_change'),
                               ('discord', '_apply_discord_change'),
                               ('google_chat', '_apply_google_chat_change'),
                               ('teams', '_apply_teams_change')):
            setattr(svc, meth, MagicMock(return_value={'success': True,
                                                       'plat': platform}))
            r = svc._apply_change_to_platform(
                workspace=ws, target_platform=platform, change_type='x',
                change_data={}, conflict_resolution=
                SyncConflictResolution.LATEST_WINS)
            assert r['plat'] == platform
        # unknown platform + missing platform id
        assert svc._apply_change_to_platform(
            ws, 'irc', 'x', {}, 'latest')['success'] is False
        empty = _ws(slack_workspace_id=None)
        assert svc._apply_change_to_platform(
            empty, 'slack', 'x', {}, 'latest')['success'] is False

    def test_apply_slack_change(self, svc):
        with patch('integrations.slack_enhanced_service.'
                   'SlackEnhancedService'):
            assert svc._apply_slack_change('T1', 'name_change',
                                           {'new_name': 'N'})['success']
            assert svc._apply_slack_change(
                'T1', 'member_add', {'email': 'e'})['success']
            assert svc._apply_slack_change(
                'T1', 'member_remove', {'user_id': 'u'})['success']
            assert svc._apply_slack_change(
                'T1', 'channel_add', {'channel_name': 'c'})['success']
            assert svc._apply_slack_change(
                'T1', 'channel_remove', {'channel_id': 'c'})['success']
            assert svc._apply_slack_change('T1', 'settings_change',
                                           {})['success']
            # missing data fallthroughs
            for ct, data in (('member_add', {}), ('member_remove', {}),
                             ('channel_add', {}), ('channel_remove', {})):
                r = svc._apply_slack_change('T1', ct, data)
                assert r['success'] is False, ct
        # ImportError branch
        fake_mod = types.ModuleType('integrations.slack_enhanced_service')
        with patch.dict(sys.modules,
                        {'integrations.slack_enhanced_service': fake_mod}):
            r = svc._apply_slack_change('T1', 'name_change', {})
            assert 'unavailable' in r['error']
        # generic exception
        with patch('integrations.slack_enhanced_service.'
                   'SlackEnhancedService', side_effect=RuntimeError('x')):
            r = svc._apply_slack_change('T1', 'name_change', {})
            assert r['success'] is False

    def test_apply_discord_change(self, svc):
        with patch('integrations.atom_discord_integration.'
                   'atom_discord_integration', MagicMock()):
            assert svc._apply_discord_change('G', 'name_change',
                                             {'new_name': 'N'})['success']
            assert svc._apply_discord_change(
                'G', 'member_add', {'user_id': 'u'})['success']
            assert svc._apply_discord_change(
                'G', 'member_remove', {'user_id': 'u'})['success']
            assert svc._apply_discord_change(
                'G', 'channel_add', {'channel_name': 'c',
                                     'channel_type': 'voice'})['success']
            assert svc._apply_discord_change(
                'G', 'channel_remove', {'channel_id': 'c'})['success']
            assert svc._apply_discord_change('G', 'desc', {})['success']
            for ct in ('name_change', 'member_add', 'member_remove',
                       'channel_add', 'channel_remove'):
                assert svc._apply_discord_change('G', ct, {})['success'] is \
                    False
        with patch('integrations.atom_discord_integration.'
                   'atom_discord_integration', None):
            r = svc._apply_discord_change('G', 'name_change', {})
            assert r['success'] is False and 'not available' in r['error']
        empty = types.ModuleType('integrations.atom_discord_integration')
        with patch.dict(sys.modules,
                        {'integrations.atom_discord_integration': empty}):
            assert 'unavailable' in svc._apply_discord_change(
                'G', 'name_change', {})['error']
        # generic exception branch (module attribute access raises)
        class BoomMod(types.ModuleType):
            def __getattr__(self, item):
                raise RuntimeError('x')
        with patch.dict(sys.modules,
                        {'integrations.atom_discord_integration':
                         BoomMod('x')}):
            r = svc._apply_discord_change('G', 'name_change', {})
            assert r['success'] is False

    def test_apply_google_chat_change(self, svc):
        with patch('integrations.atom_google_chat_integration.'
                   'atom_google_chat_integration', MagicMock()):
            assert svc._apply_google_chat_change(
                'S', 'name_change', {'new_name': 'N'})['success']
            assert svc._apply_google_chat_change(
                'S', 'member_add', {'email': 'e'})['success']
            assert svc._apply_google_chat_change(
                'S', 'member_remove', {'member_name': 'm'})['success']
            assert svc._apply_google_chat_change('S', 'channel_add',
                                                 {})['success']
            assert svc._apply_google_chat_change('S', 'channel_remove',
                                                 {})['success']
            assert svc._apply_google_chat_change('S', 'other', {})['success']
            for ct in ('name_change', 'member_add', 'member_remove'):
                assert svc._apply_google_chat_change('S', ct,
                                                     {})['success'] is False
        with patch('integrations.atom_google_chat_integration.'
                   'atom_google_chat_integration', None):
            assert svc._apply_google_chat_change(
                'S', 'name_change', {})['success'] is False

    def test_apply_teams_change(self, svc):
        with patch('integrations.atom_teams_integration.'
                   'atom_teams_integration', MagicMock()):
            assert svc._apply_teams_change(
                'TM', 'name_change', {'new_name': 'N'})['success']
            assert svc._apply_teams_change(
                'TM', 'member_add', {'email': 'e'})['success']
            assert svc._apply_teams_change(
                'TM', 'member_remove', {'user_id': 'u'})['success']
            assert svc._apply_teams_change(
                'TM', 'channel_add', {'channel_name': 'c'})['success']
            assert svc._apply_teams_change(
                'TM', 'channel_remove', {'channel_id': 'c'})['success']
            assert svc._apply_teams_change('TM', 'other', {})['success']
            for ct in ('name_change', 'member_add', 'member_remove',
                       'channel_add', 'channel_remove'):
                assert svc._apply_teams_change('TM', ct,
                                               {})['success'] is False
        with patch('integrations.atom_teams_integration.'
                   'atom_teams_integration', None):
            assert svc._apply_teams_change(
                'TM', 'name_change', {})['success'] is False
