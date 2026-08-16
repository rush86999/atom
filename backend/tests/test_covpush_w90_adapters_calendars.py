# -*- coding: utf-8 -*-
"""Coverage wave 90 — Airtable/HubSpot/Stripe/Jira adapters plus
Outlook/Google calendar services.

No network: all httpx / aiohttp / googleapiclient / msal boundaries mocked.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

import core.integrations.adapters.airtable as airtable_mod
from core.integrations.adapters.airtable import AirtableAdapter
import core.integrations.adapters.hubspot as hubspot_mod
from core.integrations.adapters.hubspot import HubSpotAdapter
import core.integrations.adapters.stripe as stripe_mod
from core.integrations.adapters.stripe import StripeAdapter
import core.integrations.adapters.jira as jira_mod
from core.integrations.adapters.jira import JiraAdapter
import integrations.outlook_calendar_service as outlook_cal_mod
from integrations.outlook_calendar_service import OutlookCalendarService
import integrations.google_calendar_service as gcal_mod
from integrations.google_calendar_service import GoogleCalendarService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resp(payload=None, status=200, error=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    if error is not None:
        r.raise_for_status.side_effect = error
    r.text = 'body'
    return r


def _status_error():
    return httpx.HTTPStatusError(
        'boom', request=httpx.Request('GET', 'http://x'),
        response=MagicMock())


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient used as an async context manager."""

    def __init__(self):
        self.get = AsyncMock(return_value=_resp({}))
        self.post = AsyncMock(return_value=_resp({}))
        self.patch = AsyncMock(return_value=_resp({}))
        self.put = AsyncMock(return_value=_resp({}))
        self.delete = AsyncMock(return_value=_resp({}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


def _patch_http(mod, client):
    return patch.object(mod.httpx, 'AsyncClient', lambda: client)


def _db_with_token(token=None):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = token
    return db


def _token_row(**kw):
    row = MagicMock()
    row.access_token = kw.get('access_token', 'enc-acc')
    row.refresh_token = kw.get('refresh_token', 'enc-ref')
    row.expires_at = kw.get('expires_at')
    row.instance_url = kw.get('instance_url')
    return row


def _ident(v, allow_plaintext=False):
    return v


# ===========================================================================
# AirtableAdapter
# ===========================================================================

class TestAirtableAdapter:

    def _adapter(self, db=None):
        with patch.dict('os.environ', {'AIRTABLE_CLIENT_ID': 'cid',
                                       'AIRTABLE_CLIENT_SECRET': 'sec',
                                       'AIRTABLE_REDIRECT_URI': 'http://cb',
                                       'AIRTABLE_PAT': ''}):
            return AirtableAdapter(db, 'ws1')

    def test_load_token(self):
        a = self._adapter(db=_db_with_token(_token_row()))
        with patch('core.privsec.token_encryption.decrypt_token', _ident):
            asyncio.run(a._load_token())
        assert a._access_token == 'enc-acc'
        assert a._refresh_token == 'enc-ref'

    def test_load_token_no_db_and_no_row(self):
        a = self._adapter()
        asyncio.run(a._load_token())  # no db -> no-op
        a2 = self._adapter(db=_db_with_token(None))
        asyncio.run(a2._load_token())
        assert a2._access_token is None

    def test_refresh_token_no_token(self):
        a = self._adapter()
        assert asyncio.run(a.refresh_token()) is False

    def test_refresh_token_success_and_db_update(self):
        a = self._adapter(db=_db_with_token(_token_row()))
        a._refresh_token = 'r1'
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'a2',
                                          'refresh_token': 'r2',
                                          'expires_in': 60})
        with _patch_http(airtable_mod, client), \
             patch('core.models.IntegrationToken', MagicMock()), \
             patch('core.privsec.token_encryption.decrypt_token', _ident), \
             patch('core.privsec.token_encryption.encrypt_token', _ident), \
             patch('core.privsec.token_encryption.stamp_credential_metadata'):
            assert asyncio.run(a.refresh_token()) is True
        assert a._access_token == 'a2'
        assert a.db.commit.called

    def test_refresh_token_failure(self):
        a = self._adapter()
        a._refresh_token = 'r1'
        client = _FakeAsyncClient()
        client.post.return_value = _resp({}, error=RuntimeError('net'))
        with _patch_http(airtable_mod, client):
            assert asyncio.run(a.refresh_token()) is False

    def test_ensure_token_branches(self):
        # loads from db and keeps token
        a = self._adapter(db=_db_with_token(_token_row()))
        with patch('core.privsec.token_encryption.decrypt_token', _ident):
            asyncio.run(a.ensure_token())
        assert a._access_token == 'enc-acc'
        # expired with refresh token -> refresh path
        a2 = self._adapter()
        a2._access_token = None
        a2.personal_access_token = None
        a2._refresh_token = None
        asyncio.run(a2.ensure_token())
        # PAT fallback
        a3 = self._adapter()
        a3.personal_access_token = 'pat'
        a3._access_token = None
        a3._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        a3._refresh_token = None
        asyncio.run(a3.ensure_token())
        assert a3._access_token == 'pat'
        # expired with refresh token -> refresh_token() invoked
        a4 = self._adapter()
        a4._access_token = 'at'
        a4._token_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        a4._refresh_token = 'r'
        with patch.object(AirtableAdapter, 'refresh_token',
                          return_value=True) as rt:
            asyncio.run(a4.ensure_token())
        rt.assert_called_once()

    def test_get_oauth_url(self):
        a = self._adapter()
        url = asyncio.run(a.get_oauth_url())
        assert 'airtable.com/oauth2/v1/authorize' in url
        a2 = self._adapter()
        a2.client_id = None
        with pytest.raises(ValueError):
            asyncio.run(a2.get_oauth_url())

    def test_exchange_code(self):
        a = self._adapter()
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'at',
                                          'refresh_token': 'rt',
                                          'expires_in': 120})
        with _patch_http(airtable_mod, client):
            data = asyncio.run(a.exchange_code_for_token('code'))
        assert data['access_token'] == 'at'
        # error branch
        client2 = _FakeAsyncClient()
        client2.post.return_value = _resp({}, error=_status_error())
        with _patch_http(airtable_mod, client2):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(a.exchange_code_for_token('bad'))
        # missing creds
        a2 = self._adapter()
        a2.client_secret = None
        with pytest.raises(ValueError):
            asyncio.run(a2.exchange_code_for_token('c'))

    def test_test_connection(self):
        a = self._adapter()
        assert asyncio.run(a.test_connection()) is False
        a._access_token = 'at'
        client = _FakeAsyncClient()
        with _patch_http(airtable_mod, client):
            assert asyncio.run(a.test_connection()) is True
        client.get.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(airtable_mod, client):
            assert asyncio.run(a.test_connection()) is False

    @pytest.mark.parametrize('meth,args,kw', [
        ('list_bases', (), {}),
        ('list_tables', ('b1',), {}),
        ('get_records', ('b1', 't1'), {'filter_by_formula': 'F',
                                       'sort': [{'field': 'N',
                                                 'direction': 'desc'}]}),
        ('get_record', ('b1', 't1', 'r1'), {}),
        ('create_record', ('b1', 't1'), {'fields': {'a': 1}}),
        ('update_record', ('b1', 't1', 'r1'), {'fields': {'a': 2}}),
        ('delete_record', ('b1', 't1', 'r1'), {}),
        ('search_records', ('b1', 't1'), {'field_name': 'N',
                                          'search_value': 'v'}),
    ])
    def test_crud_ok(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        payload = {'bases': [{'id': 'b1'}], 'tables': [{'id': 't'}],
                   'records': [{'id': 'r1'}]}
        for m in ('get', 'post', 'patch', 'delete'):
            getattr(client, m).return_value = _resp(payload)
        with _patch_http(airtable_mod, client):
            res = asyncio.run(getattr(a, meth)(*args, **kw))
        assert res is not None or meth == 'delete_record'

    @pytest.mark.parametrize('meth,args,kw', [
        ('list_bases', (), {}), ('list_tables', ('b1',), {}),
        ('get_records', ('b1', 't1'), {}), ('get_record', ('b1', 't1', 'r1'), {}),
        ('create_record', ('b1', 't1'), {'fields': {}}),
        ('update_record', ('b1', 't1', 'r1'), {'fields': {}}),
        ('search_records', ('b1', 't1'), {'field_name': 'f',
                                          'search_value': 'v'}),
        ('delete_record', ('b1', 't1', 'r1'), {}),
    ])
    def test_crud_no_token_raises(self, meth, args, kw):
        a = self._adapter()
        with pytest.raises(ValueError):
            asyncio.run(getattr(a, meth)(*args, **kw))

    @pytest.mark.parametrize('meth,args,kw', [
        ('list_bases', (), {}), ('list_tables', ('b1',), {}),
        ('get_records', ('b1', 't1'), {}), ('get_record', ('b1', 't1', 'r1'), {}),
        ('create_record', ('b1', 't1'), {'fields': {}}),
        ('update_record', ('b1', 't1', 'r1'), {'fields': {}}),
        ('search_records', ('b1', 't1'), {'field_name': 'f',
                                          'search_value': 'v'}),
    ])
    def test_crud_error_branch(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post', 'patch', 'delete'):
            r = _resp({}, error=RuntimeError('net'))
            getattr(client, m).return_value = r
        with _patch_http(airtable_mod, client):
            with pytest.raises(RuntimeError):
                asyncio.run(getattr(a, meth)(*args, **kw))

    def test_delete_record_error_returns_false(self):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        client.delete.return_value = _resp({}, error=RuntimeError('net'))
        with _patch_http(airtable_mod, client):
            assert asyncio.run(a.delete_record('b', 't', 'r')) is False

    def test_search_records_no_token(self):
        a = self._adapter()
        with pytest.raises(ValueError):
            asyncio.run(a.search_records('b', 't', 'f', 'v'))

    def test_get_available_schemas(self):
        a = self._adapter()
        a._access_token = 'at'
        a.list_bases = AsyncMock(return_value=[
            {'id': 'b1', 'name': 'Base One'},
            {'id': 'b2', 'name': 'Base Two'},
        ])
        a.list_tables = AsyncMock(side_effect=[
            [{'id': 't1'}], RuntimeError('boom'),
        ])
        schemas = asyncio.run(a.get_available_schemas())
        assert len(schemas) == 1
        assert schemas[0]['base_id'] == 'b1'
        # total failure
        a.list_bases = AsyncMock(side_effect=RuntimeError('x'))
        assert asyncio.run(a.get_available_schemas()) == []

    def test_fetch_records(self):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        client.get.return_value = _resp({'records': [{'id': 'r'}],
                                         'offset': 'off1'})
        with _patch_http(airtable_mod, client):
            res = asyncio.run(a.fetch_records('b1:t1', after='o0'))
        assert res['results'] == [{'id': 'r'}]
        assert res['paging'] == {'after': 'off1'}
        # invalid entity type
        with _patch_http(airtable_mod, client):
            res = asyncio.run(a.fetch_records('nope'))
        assert res == {'results': [], 'paging': {}}
        # no more pages
        client.get.return_value = _resp({'records': []})
        with _patch_http(airtable_mod, client):
            res = asyncio.run(a.fetch_records('b1:t1'))
        assert res['paging'] == {}
        # error branch
        client.get.return_value = _resp({}, error=RuntimeError('net'))
        with _patch_http(airtable_mod, client):
            res = asyncio.run(a.fetch_records('b1:t1'))
        assert res == {'results': [], 'paging': {}}
        # no token
        a2 = self._adapter()
        with pytest.raises(ValueError):
            asyncio.run(a2.fetch_records('b:t'))


# ===========================================================================
# HubSpotAdapter
# ===========================================================================

class TestHubSpotAdapter:

    def _adapter(self, db=None):
        with patch.dict('os.environ', {'HUBSPOT_CLIENT_ID': 'cid',
                                       'HUBSPOT_CLIENT_SECRET': 'sec',
                                       'HUBSPOT_REDIRECT_URI': 'http://cb'}):
            return HubSpotAdapter(db, 'ws1')

    def test_load_token(self):
        a = self._adapter(db=_db_with_token(_token_row(refresh_token=None)))
        with patch('core.privsec.token_encryption.decrypt_token', _ident):
            asyncio.run(a._load_token())
        assert a._access_token == 'enc-acc'
        assert a._refresh_token is None
        a2 = self._adapter()
        asyncio.run(a2._load_token())

    def test_refresh_token(self):
        a = self._adapter()
        assert asyncio.run(a.refresh_token()) is False
        a._refresh_token = 'r1'
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'a2',
                                          'expires_in': 60})
        db = _db_with_token(_token_row())
        a.db = db
        with _patch_http(hubspot_mod, client), \
             patch('core.models.IntegrationToken', MagicMock()), \
             patch('core.privsec.token_encryption.encrypt_token', _ident), \
             patch('core.privsec.token_encryption.stamp_credential_metadata'):
            assert asyncio.run(a.refresh_token()) is True
        client.post.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(hubspot_mod, client):
            assert asyncio.run(a.refresh_token()) is False

    def test_ensure_token(self):
        a = self._adapter(db=_db_with_token(None))
        asyncio.run(a.ensure_token())
        a2 = self._adapter()
        a2._access_token = 'at'
        a2._token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        a2._refresh_token = None
        asyncio.run(a2.ensure_token())
        a3 = self._adapter()
        a3._access_token = 'at'
        a3._token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        a3._refresh_token = 'r'
        with patch.object(HubSpotAdapter, 'refresh_token',
                          return_value=True) as rt:
            asyncio.run(a3.ensure_token())
        rt.assert_called_once()

    def test_get_oauth_url(self):
        a = self._adapter()
        assert 'hubspot.com/oauth' in asyncio.run(a.get_oauth_url())
        a.client_id = None
        with pytest.raises(ValueError):
            asyncio.run(a.get_oauth_url())

    def test_exchange_code(self):
        a = self._adapter()
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'at',
                                          'expires_in': 10})
        with _patch_http(hubspot_mod, client):
            assert asyncio.run(a.exchange_code_for_token('c'))['access_token'] == 'at'
        client.post.return_value = _resp({}, error=_status_error())
        with _patch_http(hubspot_mod, client):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(a.exchange_code_for_token('bad'))
        a2 = self._adapter()
        a2.client_id = None
        with pytest.raises(ValueError):
            asyncio.run(a2.exchange_code_for_token('c'))

    def test_test_connection(self):
        a = self._adapter()
        assert asyncio.run(a.test_connection()) is False
        a._access_token = 'at'
        client = _FakeAsyncClient()
        with _patch_http(hubspot_mod, client):
            assert asyncio.run(a.test_connection()) is True
        client.get.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(hubspot_mod, client):
            assert asyncio.run(a.test_connection()) is False

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_contacts', ('q',), {'limit': 5}),
        ('get_contact', ('c1',), {}),
        ('create_contact', ('a@b.c',), {'first_name': 'F', 'last_name': 'L',
                                        'company': 'Co', 'phone': '123'}),
        ('update_contact', ('c1',), {'properties': {'x': 1}}),
        ('get_deals', (), {'limit': 5}),
        ('create_deal', ('D',), {'amount': 9.5, 'stage': 's',
                                 'pipeline': 'p', 'extra': 1}),
        ('get_available_schemas', (), {}),
        ('fetch_records', ('contact',), {'after': '5'}),
        ('fetch_records', ('deals',), {}),
    ])
    def test_methods_ok(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        payload = {'results': [{'id': 'x'}]}
        for m in ('get', 'post', 'patch'):
            getattr(client, m).return_value = _resp(payload)
        with _patch_http(hubspot_mod, client):
            res = asyncio.run(getattr(a, meth)(*args, **kw))
        assert res is not None

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_contacts', ('q',), {}), ('get_contact', ('c',), {}),
        ('create_contact', ('a@b.c',), {}),
        ('update_contact', ('c',), {'properties': {}}),
        ('get_deals', (), {}), ('create_deal', ('D',), {}),
        ('get_available_schemas', (), {}), ('fetch_records', ('contacts',), {}),
    ])
    def test_methods_no_token(self, meth, args, kw):
        a = self._adapter()
        with pytest.raises(ValueError):
            asyncio.run(getattr(a, meth)(*args, **kw))

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_contacts', ('q',), {}),
        ('get_contact', ('c',), {}),
        ('create_contact', ('a@b.c',), {}),
        ('update_contact', ('c',), {'properties': {}}),
        ('get_deals', (), {}),
        ('create_deal', ('D',), {}),
    ])
    def test_methods_error_raises(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post', 'patch'):
            getattr(client, m).return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(hubspot_mod, client):
            with pytest.raises(RuntimeError):
                asyncio.run(getattr(a, meth)(*args, **kw))

    def test_schema_and_fetch_error_branches(self):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        client.get.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(hubspot_mod, client):
            assert asyncio.run(a.get_available_schemas()) == []
            res = asyncio.run(a.fetch_records('contacts'))
        assert res == {'results': [], 'paging': {}}


# ===========================================================================
# StripeAdapter
# ===========================================================================

class TestStripeAdapter:

    def _adapter(self):
        with patch.dict('os.environ', {'STRIPE_CLIENT_ID': 'cid',
                                       'STRIPE_SECRET_KEY': 'sec',
                                       'STRIPE_REDIRECT_URI': 'http://cb'}):
            return StripeAdapter(None, 'ws1')

    def test_get_oauth_url(self):
        a = self._adapter()
        assert 'connect.stripe.com' in asyncio.run(a.get_oauth_url())
        a.client_id = None
        with pytest.raises(ValueError):
            asyncio.run(a.get_oauth_url())

    def test_exchange_code(self):
        a = self._adapter()
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'at',
                                          'refresh_token': 'rt',
                                          'stripe_user_id': 'u'})
        with _patch_http(stripe_mod, client):
            res = asyncio.run(a.exchange_code_for_token('c'))
        assert res['stripe_user_id'] == 'u'
        client.post.return_value = _resp({}, error=_status_error())
        with _patch_http(stripe_mod, client):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(a.exchange_code_for_token('bad'))
        a2 = self._adapter()
        a2.client_secret = None
        with pytest.raises(ValueError):
            asyncio.run(a2.exchange_code_for_token('c'))

    def test_test_connection(self):
        a = self._adapter()
        assert asyncio.run(a.test_connection()) is False
        a._access_token = 'at'
        client = _FakeAsyncClient()
        with _patch_http(stripe_mod, client):
            assert asyncio.run(a.test_connection()) is True
        client.get.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(stripe_mod, client):
            assert asyncio.run(a.test_connection()) is False

    @pytest.mark.parametrize('meth,args,kw', [
        ('get_customers', (), {'starting_after': 'cus_1'}),
        ('get_customer', ('cus_1',), {}),
        ('create_customer', (), {'name': 'N', 'email': 'a@b.c',
                                 'description': 'd', 'meta': 'x'}),
        ('get_charges', (), {'created': {'gte': 1, 'lte': 2}}),
        ('create_charge', (100, 'usd'), {'customer': 'cus_1',
                                         'description': 'd', 'meta': 'x'}),
        ('get_invoices', (), {'customer': 'cus_1'}),
        ('get_subscriptions', (), {'customer': 'cus_1'}),
        ('create_payment_intent', (200, 'usd'), {'customer': 'cus_1',
                                                 'metadata': {'k': 'v'}}),
    ])
    def test_methods_ok(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post'):
            getattr(client, m).return_value = _resp({'data': [{'id': 'x'}],
                                                     'id': 'new'})
        with _patch_http(stripe_mod, client):
            res = asyncio.run(getattr(a, meth)(*args, **kw))
        assert res is not None

    @pytest.mark.parametrize('meth,args', [
        ('get_customers', ()), ('get_customer', ('c',)),
        ('create_customer', ()), ('get_charges', ()),
        ('create_charge', (1, 'usd')), ('get_invoices', ()),
        ('get_subscriptions', ()), ('create_payment_intent', (1, 'usd')),
    ])
    def test_methods_no_token(self, meth, args):
        a = self._adapter()
        with pytest.raises(ValueError):
            asyncio.run(getattr(a, meth)(*args))

    @pytest.mark.parametrize('meth,args,kw', [
        ('get_customers', (), {}), ('get_customer', ('c',), {}),
        ('create_customer', (), {}), ('get_charges', (), {}),
        ('create_charge', (1, 'usd'), {}), ('get_invoices', (), {}),
        ('get_subscriptions', (), {}), ('create_payment_intent', (1, 'usd'), {}),
    ])
    def test_methods_error_raises(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post'):
            getattr(client, m).return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(stripe_mod, client):
            with pytest.raises(RuntimeError):
                asyncio.run(getattr(a, meth)(*args, **kw))


# ===========================================================================
# JiraAdapter
# ===========================================================================

class TestJiraAdapter:

    def _adapter(self, db=None):
        with patch.dict('os.environ', {'JIRA_CLIENT_ID': 'cid',
                                       'JIRA_CLIENT_SECRET': 'sec',
                                       'JIRA_REDIRECT_URI': 'http://cb',
                                       'JIRA_SITE_URL': 'https://j.example'}):
            return JiraAdapter(db, 'ws1')

    def test_load_token_with_instance_url(self):
        a = self._adapter()
        a.site_url = None
        a.base_url = None
        row = _token_row(instance_url='https://inst.example')
        a.db = _db_with_token(row)
        with patch('core.privsec.token_encryption.decrypt_token', _ident):
            asyncio.run(a._load_token())
        assert a.site_url == 'https://inst.example'
        assert a.base_url.endswith('/rest/api/3')
        # no token row
        a2 = self._adapter(db=_db_with_token(None))
        asyncio.run(a2._load_token())
        # no db
        a3 = self._adapter()
        a3.db = None
        asyncio.run(a3._load_token())

    def test_refresh_token(self):
        a = self._adapter()
        assert asyncio.run(a.refresh_token()) is False
        a._refresh_token = 'r1'
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'a2',
                                          'refresh_token': 'r2',
                                          'expires_in': 60})
        a.db = _db_with_token(_token_row())
        with _patch_http(jira_mod, client), \
             patch('core.models.IntegrationToken', MagicMock()), \
             patch('core.privsec.token_encryption.encrypt_token', _ident), \
             patch('core.privsec.token_encryption.stamp_credential_metadata'):
            assert asyncio.run(a.refresh_token()) is True
        client.post.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(jira_mod, client):
            assert asyncio.run(a.refresh_token()) is False

    def test_ensure_token(self):
        a = self._adapter(db=_db_with_token(None))
        asyncio.run(a.ensure_token())
        a2 = self._adapter()
        a2._access_token = 'at'
        a2._token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        a2._refresh_token = None
        asyncio.run(a2.ensure_token())
        a3 = self._adapter()
        a3._access_token = 'at'
        a3._token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        a3._refresh_token = 'r'
        with patch.object(JiraAdapter, 'refresh_token',
                          return_value=True) as rt:
            asyncio.run(a3.ensure_token())
        rt.assert_called_once()

    def test_get_oauth_url(self):
        a = self._adapter()
        assert 'authorization' in asyncio.run(a.get_oauth_url())
        a2 = self._adapter()
        a2.site_url = None
        with pytest.raises(ValueError):
            asyncio.run(a2.get_oauth_url())

    def test_exchange_code(self):
        a = self._adapter()
        client = _FakeAsyncClient()
        client.post.return_value = _resp({'access_token': 'at',
                                          'expires_in': 10})
        with _patch_http(jira_mod, client):
            assert asyncio.run(a.exchange_code_for_token('c'))['access_token'] == 'at'
        client.post.return_value = _resp({}, error=_status_error())
        with _patch_http(jira_mod, client):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(a.exchange_code_for_token('bad'))
        a2 = self._adapter()
        a2.client_secret = None
        with pytest.raises(ValueError):
            asyncio.run(a2.exchange_code_for_token('c'))

    def test_test_connection(self):
        a = self._adapter()
        assert asyncio.run(a.test_connection()) is False
        a._access_token = 'at'
        client = _FakeAsyncClient()
        with _patch_http(jira_mod, client):
            assert asyncio.run(a.test_connection()) is True
        client.get.return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(jira_mod, client):
            assert asyncio.run(a.test_connection()) is False

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_issues', ('project = X',), {'limit': 5}),
        ('get_issue', ('X-1',), {}),
        ('create_issue', ('X', 'sum', 'desc'), {'issue_type': 'Bug',
                                                'priority': 'High'}),
        ('update_issue', ('X-1',), {'updates': {'summary': 's'}}),
        ('add_comment', ('X-1', 'hello'), {}),
        ('get_available_schemas', (), {}),
        ('fetch_records', ('X:Bug',), {'after': '10'}),
        ('fetch_records', ('X:Task',), {}),
    ])
    def test_methods_ok(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        payload = {'issues': [{'key': 'X-1'}], 'total': 5,
                   'key': 'X-9', 'id': '1'}
        projects = [{'key': 'X', 'name': 'Proj',
                     'issueTypes': [{'name': 'Bug', 'id': '1',
                                     'description': 'd'}]}]
        client.get.return_value = _resp(projects)
        client.post.return_value = _resp(payload)
        client.put.return_value = _resp(payload)
        with _patch_http(jira_mod, client):
            res = asyncio.run(getattr(a, meth)(*args, **kw))
        assert res is not None or meth == 'add_comment'

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_issues', ('jql',), {}), ('get_issue', ('X-1',), {}),
        ('create_issue', ('X', 's', 'd'), {}),
        ('update_issue', ('X-1',), {'updates': {}}),
        ('add_comment', ('X-1', 'c'), {}),
        ('get_available_schemas', (), {}),
        ('fetch_records', ('X:Bug',), {}),
    ])
    def test_methods_no_config(self, meth, args, kw):
        a = self._adapter()
        a._access_token = None
        with pytest.raises(ValueError):
            asyncio.run(getattr(a, meth)(*args, **kw))

    @pytest.mark.parametrize('meth,args,kw', [
        ('search_issues', ('jql',), {}), ('get_issue', ('X-1',), {}),
        ('create_issue', ('X', 's', 'd'), {}),
        ('update_issue', ('X-1',), {'updates': {}}),
        ('add_comment', ('X-1', 'c'), {}),
    ])
    def test_methods_error_raises(self, meth, args, kw):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post', 'put'):
            getattr(client, m).return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(jira_mod, client):
            with pytest.raises(RuntimeError):
                asyncio.run(getattr(a, meth)(*args, **kw))

    def test_schema_and_fetch_error_branches(self):
        a = self._adapter()
        a._access_token = 'at'
        client = _FakeAsyncClient()
        for m in ('get', 'post'):
            getattr(client, m).return_value = _resp({}, error=RuntimeError('x'))
        with _patch_http(jira_mod, client):
            assert asyncio.run(a.get_available_schemas()) == []
            assert asyncio.run(a.fetch_records('X:Bug')) == {'results': [],
                                                             'paging': {}}
            # invalid entity format
            assert asyncio.run(a.fetch_records('nope')) == {'results': [],
                                                            'paging': {}}


# ===========================================================================
# OutlookCalendarService
# ===========================================================================

def _aiohttp_session_mock(get=None, post=None, patch_=None, delete=None):
    session = MagicMock()
    for name, resp in (('get', get), ('post', post),
                       ('patch', patch_), ('delete', delete)):
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=resp)
        cm.__aexit__ = AsyncMock(return_value=False)
        setattr(session, name, MagicMock(return_value=cm))
    return session


def _aio_resp(payload=None, status=200):
    r = MagicMock()
    r.status = status
    r.json = AsyncMock(return_value=payload if payload is not None else {})
    r.text = AsyncMock(return_value='err-body')
    return r


def _graph_event(event_id='e1', subject='S'):
    return {
        'id': event_id,
        'subject': subject,
        'body': {'contentType': 'text', 'content': 'desc'},
        'start': {'dateTime': '2026-01-01T09:00:00', 'timeZone': 'UTC'},
        'end': {'dateTime': '2026-01-01T10:00:00', 'timeZone': 'UTC'},
        'attendees': [{'emailAddress': {'address': 'a@b.c'}},
                      {'emailAddress': {}}],
        'location': {'displayName': 'Room 1'},
        'createdDateTime': 'c', 'lastModifiedDateTime': 'u',
    }


class TestOutlookCalendarService:

    def _service(self, tmp_path=None):
        svc = OutlookCalendarService(tenant_id='t1', config={'client_id': 'cid'})
        svc.access_token = 'tok'
        svc.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        if tmp_path is not None:
            svc.token_cache_file = tmp_path / 'cache.json'
        return svc

    def test_token_cache_roundtrip(self, tmp_path):
        svc = self._service(tmp_path)
        assert svc._load_token_cache() == {}
        svc._save_token_cache({'a': 1})
        assert svc._load_token_cache() == {'a': 1}
        bad = tmp_path / 'bad.json'
        bad.write_text('not-json')
        svc.token_cache_file = bad
        assert svc._load_token_cache() == {}

    def test_authenticate_no_client_id(self):
        svc = OutlookCalendarService(tenant_id='t1', config={})
        svc.client_id = None
        assert svc.authenticate() is False

    def test_authenticate_silent(self):
        svc = self._service()
        app = MagicMock()
        app.get_accounts.return_value = [MagicMock()]
        app.acquire_token_silent.return_value = {'access_token': 't',
                                                 'expires_in': 60}
        with patch.object(outlook_cal_mod, 'PublicClientApplication',
                          return_value=app):
            assert svc.authenticate() is True

    def test_authenticate_device_flow(self):
        svc = self._service()
        app = MagicMock()
        app.get_accounts.return_value = []
        app.initiate_device_flow.return_value = {'user_code': 'ABC',
                                                 'message': 'go here'}
        app.acquire_token_by_device_flow.return_value = {'access_token': 't'}
        with patch.object(outlook_cal_mod, 'PublicClientApplication',
                          return_value=app), \
             patch('builtins.print'):
            assert svc.authenticate() is True
        # failed device flow result
        app.acquire_token_by_device_flow.return_value = {'error': 'bad'}
        with patch.object(outlook_cal_mod, 'PublicClientApplication',
                          return_value=app), \
             patch('builtins.print'):
            assert svc.authenticate() is False
        # flow without user_code -> exception path
        app.initiate_device_flow.return_value = {}
        with patch.object(outlook_cal_mod, 'PublicClientApplication',
                          return_value=app):
            assert svc.authenticate() is False

    def test_ensure_authenticated_reauth(self):
        svc = self._service()
        svc.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            assert svc._ensure_authenticated() is False
        svc.access_token = 'tok'
        svc.token_expiry = datetime.now(timezone.utc) + timedelta(minutes=1)
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=True):
            assert svc._ensure_authenticated() is True
        svc.token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        assert svc._ensure_authenticated() is True

    def test_get_events(self):
        svc = self._service()
        resp = _aio_resp({'value': [_graph_event()]})
        session = _aiohttp_session_mock(get=resp)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(session))):
            events = asyncio.run(svc.get_events())
        assert events[0]['platform'] == 'outlook'
        # error status
        resp2 = _aio_resp({}, status=500)
        session2 = _aiohttp_session_mock(get=resp2)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(session2))):
            assert asyncio.run(svc.get_events(time_min=datetime(2026, 1, 1),
                                              time_max=datetime(2026, 1, 2))) == []
        # unauthenticated
        svc.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc.get_events()) == []

    def test_create_event(self):
        svc = self._service()
        resp = _aio_resp(_graph_event('new1'), status=201)
        session = _aiohttp_session_mock(post=resp)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(session))):
            ev = asyncio.run(svc.create_event({'title': 'T',
                                               'description': 'd',
                                               'start_time': '2026-01-01T09:00:00',
                                               'end_time': '2026-01-01T10:00:00',
                                               'location': 'L',
                                               'attendees': ['a@b.c']}))
        assert ev['id'] == 'new1'
        # failure status + unauthenticated
        resp2 = _aio_resp({}, status=400)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(
                              _aiohttp_session_mock(post=resp2)))):
            assert asyncio.run(svc.create_event({'title': 'x'})) is None
        svc2 = self._service()
        svc2.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.create_event({})) is None

    def test_update_event(self):
        svc = self._service()
        resp = _aio_resp(_graph_event('e1', 'Updated'))
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(
                              _aiohttp_session_mock(patch_=resp)))):
            ev = asyncio.run(svc.update_event('e1', {
                'title': 'Updated', 'description': 'd',
                'start_time': '2026-01-01T09:00:00',
                'end_time': '2026-01-01T10:00:00'}))
        assert ev['title'] == 'Updated'
        resp2 = _aio_resp({}, status=400)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(
                              _aiohttp_session_mock(patch_=resp2)))):
            assert asyncio.run(svc.update_event('e1', {})) is None
        svc2 = self._service()
        svc2.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.update_event('e1', {})) is None

    def test_delete_event(self):
        svc = self._service()
        resp = _aio_resp(None, status=204)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(
                              _aiohttp_session_mock(delete=resp)))):
            assert asyncio.run(svc.delete_event('e1')) is True
        resp2 = _aio_resp(None, status=400)
        with patch.object(outlook_cal_mod.aiohttp, 'ClientSession',
                          MagicMock(return_value=_ctx(
                              _aiohttp_session_mock(delete=resp2)))):
            assert asyncio.run(svc.delete_event('e1')) is False
        svc2 = self._service()
        svc2.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.delete_event('e1')) is False

    def test_check_conflicts(self):
        svc = self._service()
        events = [{'id': 'e1', 'title': 'Busy',
                   'start_time': '2026-01-01T09:00:00Z',
                   'end_time': '2026-01-01T10:00:00Z'}]
        with patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=events)):
            res = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, tzinfo=timezone.utc)))
        assert res['has_conflicts'] is True and res['conflict_count'] == 1
        # no overlap
        with patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=events)):
            res = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 11, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 12, tzinfo=timezone.utc)))
        assert res['has_conflicts'] is False
        # exception branch
        with patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError('x'))):
            res = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, tzinfo=timezone.utc),
                datetime(2026, 1, 2, tzinfo=timezone.utc)))
        assert res['success'] is False
        # unauthenticated
        svc2 = self._service()
        svc2.access_token = None
        with patch.object(OutlookCalendarService, 'authenticate',
                          return_value=False):
            res = asyncio.run(svc2.check_conflicts(
                datetime(2026, 1, 1), datetime(2026, 1, 2)))
        assert 'error' in res

    def test_conversions(self):
        svc = self._service()
        uni = svc._convert_outlook_to_unified(_graph_event())
        assert uni['attendees'] == ['a@b.c']
        out = svc._convert_unified_to_outlook(
            {'title': 'T', 'location': 'L', 'attendees': ['a@b.c']})
        assert out['location']['displayName'] == 'L'
        out2 = svc._convert_unified_to_outlook({'start': 's', 'end': 'e'})
        assert out2['start']['dateTime'] == 's'

    def test_sync_to_postgres_cache(self):
        svc = self._service()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        metric = MagicMock()
        with patch('core.database.SessionLocal', return_value=db), \
             patch('core.models.IntegrationMetric', metric), \
             patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=[{}, {}])):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is True and res['metrics_synced'] == 1
        # existing metric path
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        with patch('core.database.SessionLocal', return_value=db), \
             patch('core.models.IntegrationMetric', metric), \
             patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError('x'))):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is True
        # commit failure
        db.commit.side_effect = RuntimeError('db down')
        with patch('core.database.SessionLocal', return_value=db), \
             patch('core.models.IntegrationMetric', metric), \
             patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=[])):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is False
        # session creation failure
        db.commit.side_effect = None
        with patch('core.database.SessionLocal',
                   side_effect=RuntimeError('no db')), \
             patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=[])):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is False

    def test_full_sync_and_meta(self):
        svc = self._service()
        with patch.object(OutlookCalendarService, 'sync_to_postgres_cache',
                          AsyncMock(return_value={'success': True})):
            res = asyncio.run(svc.full_sync('ws1'))
        assert res['success'] is True
        caps = svc.get_capabilities()
        assert 'get_events' in [o['id'] for o in caps['operations']]
        hc = svc.health_check()
        assert hc['healthy'] is True

    def test_execute_operation(self):
        svc = self._service()
        # tenant mismatch
        res = asyncio.run(svc.execute_operation(
            'get_events', {}, context={'tenant_id': 'other'}))
        assert res['success'] is False
        ev = {'id': 'e'}
        with patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(return_value=[ev])):
            res = asyncio.run(svc.execute_operation('get_events', {}))
        assert res['result'] == [ev]
        with patch.object(OutlookCalendarService, 'create_event',
                          AsyncMock(return_value=ev)):
            res = asyncio.run(svc.execute_operation(
                'create_event', {'event_data': {}}))
        assert res['success'] is True
        with patch.object(OutlookCalendarService, 'create_event',
                          AsyncMock(return_value=None)):
            res = asyncio.run(svc.execute_operation(
                'create_event', {'event_data': {}}))
        assert res['success'] is False
        with patch.object(OutlookCalendarService, 'update_event',
                          AsyncMock(return_value=ev)):
            res = asyncio.run(svc.execute_operation(
                'update_event', {'event_id': 'e', 'updates': {}}))
        assert res['success'] is True
        with patch.object(OutlookCalendarService, 'delete_event',
                          AsyncMock(return_value=True)):
            res = asyncio.run(svc.execute_operation(
                'delete_event', {'event_id': 'e'}))
        assert res['success'] is True
        with patch.object(OutlookCalendarService, 'check_conflicts',
                          AsyncMock(return_value={'has_conflicts': False})):
            res = asyncio.run(svc.execute_operation(
                'check_conflicts',
                {'start_time': datetime(2026, 1, 1),
                 'end_time': datetime(2026, 1, 2)}))
        assert res['success'] is True
        # unknown op
        res = asyncio.run(svc.execute_operation('bogus', {}))
        assert res['success'] is False
        # exception branch
        with patch.object(OutlookCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError('x'))):
            res = asyncio.run(svc.execute_operation('get_events', {}))
        assert res['success'] is False


def _ctx(session):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


# ===========================================================================
# GoogleCalendarService
# ===========================================================================

def _google_service():
    svc = GoogleCalendarService(tenant_id='t1', config={})
    svc.service = MagicMock()
    return svc


def _google_event(event_id='g1'):
    return {'id': event_id, 'summary': 'S', 'description': 'd',
            'start': {'dateTime': '2026-01-01T09:00:00Z'},
            'end': {'date': '2026-01-01'},
            'attendees': [{'email': 'a@b.c'}], 'location': 'L',
            'created': 'c', 'updated': 'u'}


class TestGoogleCalendarService:

    def test_get_service_with_token(self):
        svc = _google_service()
        built = MagicMock()
        with patch.object(gcal_mod, 'Credentials', MagicMock()), \
             patch.object(gcal_mod, 'build', return_value=built):
            assert svc._get_service_with_token('tok') is built
        # no service -> authenticate path
        svc2 = GoogleCalendarService(tenant_id='t1', config={})
        svc2.service = None
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            assert svc2._get_service_with_token() is None
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=True):
            assert svc2._get_service_with_token() is svc2.service

    def test_authenticate_not_available(self):
        svc = GoogleCalendarService(tenant_id='t1', config={})
        with patch.object(gcal_mod, 'GOOGLE_APIS_AVAILABLE', False):
            assert svc.authenticate() is False

    def test_authenticate_from_saved_token(self, tmp_path):
        svc = GoogleCalendarService(tenant_id='t1',
                                    config={'token_file': str(tmp_path / 'tok')})
        creds = MagicMock()
        creds.valid = True
        built = MagicMock()
        with patch.object(gcal_mod.os.path, 'exists', return_value=True), \
             patch.object(gcal_mod.Credentials, 'from_authorized_user_file',
                          return_value=creds), \
             patch.object(gcal_mod, 'build', return_value=built):
            assert svc.authenticate() is True
        assert svc.service is built

    def test_authenticate_refresh_and_no_creds(self, tmp_path):
        svc = GoogleCalendarService(tenant_id='t1',
                                    config={'token_file': str(tmp_path / 'tok')})
        creds = MagicMock()
        creds.valid = False
        creds.expired = True
        creds.refresh_token = 'r'
        creds.to_json.return_value = '{}'
        svc.creds = creds
        with patch.object(gcal_mod.os.path, 'exists', return_value=False), \
             patch.object(gcal_mod, 'Credentials',
                          MagicMock(from_authorized_user_file=MagicMock(
                              return_value=creds))), \
             patch.object(gcal_mod, 'build', return_value=MagicMock()):
            assert svc.authenticate() is True
        # no credentials at all
        svc2 = GoogleCalendarService(tenant_id='t1',
                                     config={'token_file': str(tmp_path / 't2')})
        svc2.credentials_json = None
        svc2.creds = None
        with patch.object(gcal_mod.os.path, 'exists', return_value=False):
            assert svc2.authenticate() is False

    def test_authenticate_json_string_flow(self, tmp_path, monkeypatch):
        svc = GoogleCalendarService(
            tenant_id='t1',
            config={'token_file': str(tmp_path / 'tok'),
                    'credentials_json': '{"installed": {}}'})
        svc.creds = None
        flow = MagicMock()
        flow.authorization_url.return_value = ('http://auth', 'state')
        good_creds = MagicMock()
        good_creds.valid = True
        good_creds.to_json.return_value = '{}'
        type(flow).credentials = good_creds

        class _FakeHttpd:
            def __init__(self, app):
                self.app = app
                self.captured = []

            def handle_request(self):
                # Simulate the OAuth callback: exercise both the 200
                # (code present) and 404 (no code) branches of the app.
                def start(status, headers):
                    self.captured.append(status)

                body = self.app({'QUERY_STRING': 'code=abc123'}, start)
                assert b'Authentication successful' in b''.join(body)
                self.app({'QUERY_STRING': 'state=xyz'}, start)
                assert self.captured[-1] == '404 Not Found'

        with patch.object(gcal_mod.os.path, 'exists', return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          'from_client_config', return_value=flow), \
             patch('wsgiref.simple_server.make_server',
                   side_effect=lambda h, p, app: _FakeHttpd(app)), \
             patch('webbrowser.open'), patch('builtins.print'), \
             patch.object(gcal_mod, 'build', return_value=MagicMock()):
            flow.fetch_token = MagicMock(return_value=None)
            assert svc.authenticate() is True
        assert svc.service is not None

    def test_authenticate_oserror_port(self, tmp_path):
        svc = GoogleCalendarService(
            tenant_id='t1',
            config={'token_file': str(tmp_path / 'tok'),
                    'credentials_json': '/path/file.json'})
        svc.creds = None
        flow = MagicMock()
        flow.authorization_url.return_value = ('http://auth', 's')
        with patch.object(gcal_mod.os.path, 'exists', return_value=False), \
             patch.object(gcal_mod.InstalledAppFlow,
                          'from_client_secrets_file', return_value=flow), \
             patch('wsgiref.simple_server.make_server',
                   side_effect=OSError('port busy')), \
             patch('builtins.print'), patch('webbrowser.open'):
            assert svc.authenticate() is False

    def test_list_calendars(self):
        svc = _google_service()
        svc.service.calendarList.return_value.list.return_value.execute \
            .return_value = {'items': [{'id': 'c1'}]}
        assert asyncio.run(svc.list_calendars()) == [{'id': 'c1'}]
        # failure
        svc.service.calendarList.side_effect = RuntimeError('x')
        assert asyncio.run(svc.list_calendars()) == []
        # no service
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.list_calendars()) == []

    def test_get_events(self):
        svc = _google_service()
        svc.service.events.return_value.list.return_value.execute \
            .return_value = {'items': [_google_event()]}
        events = asyncio.run(svc.get_events(
            time_min=datetime(2026, 1, 1, tzinfo=timezone.utc),
            time_max=datetime(2026, 1, 2)))
        assert events[0]['platform'] == 'google_calendar'
        # naive datetimes branch
        events = asyncio.run(svc.get_events(time_min=datetime(2026, 1, 1),
                                            time_max=datetime(2026, 1, 2)))
        assert len(events) == 1
        # HttpError branch
        err = gcal_mod.HttpError(MagicMock(), b'')
        svc.service.events.return_value.list.return_value.execute \
            .side_effect = err
        assert asyncio.run(svc.get_events()) == []
        # no service
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        svc2.service = None
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.get_events()) == []

    def test_create_event(self):
        svc = _google_service()
        svc.service.events.return_value.insert.return_value.execute \
            .return_value = _google_event('new')
        ev = asyncio.run(svc.create_event({'title': 'T', 'location': 'L',
                                           'attendees': ['a@b.c']}))
        assert ev['id'] == 'new'
        err = gcal_mod.HttpError(MagicMock(), b'')
        svc.service.events.return_value.insert.return_value.execute \
            .side_effect = err
        assert asyncio.run(svc.create_event({'title': 'x'})) is None
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        with patch.object(GoogleCalendarService, '_get_service_with_token',
                          return_value=None):
            assert asyncio.run(svc2.create_event({'title': 'x'})) is None

    def test_update_event(self):
        svc = _google_service()
        svc.service.events.return_value.get.return_value.execute \
            .return_value = _google_event()
        svc.service.events.return_value.update.return_value.execute \
            .return_value = _google_event('g1')
        ev = asyncio.run(svc.update_event('g1', {
            'title': 'T2', 'description': 'd2',
            'start_time': '2026-01-01T09:00:00',
            'end_time': '2026-01-01T10:00:00'}))
        assert ev['id'] == 'g1'
        err = gcal_mod.HttpError(MagicMock(), b'')
        svc.service.events.return_value.get.return_value.execute \
            .side_effect = err
        assert asyncio.run(svc.update_event('g1', {})) is None
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.update_event('g1', {})) is None

    def test_delete_event(self):
        svc = _google_service()
        svc.service.events.return_value.delete.return_value.execute \
            .return_value = None
        assert asyncio.run(svc.delete_event('g1')) is True
        err = gcal_mod.HttpError(MagicMock(), b'')
        svc.service.events.return_value.delete.return_value.execute \
            .side_effect = err
        assert asyncio.run(svc.delete_event('g1')) is False
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            assert asyncio.run(svc2.delete_event('g1')) is False

    def test_check_conflicts(self):
        svc = _google_service()
        events = [{'id': 'g1', 'title': 'Busy',
                   'start_time': '2026-01-01T09:00:00Z',
                   'end_time': '2026-01-01T10:00:00Z'}]
        with patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(return_value=events)):
            res = asyncio.run(svc.check_conflicts(
                datetime(2026, 1, 1, 9, 30, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, tzinfo=timezone.utc)))
        assert res['has_conflicts'] is True
        # no overlap / naive times
        with patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(return_value=events)):
            res = asyncio.run(svc.check_conflicts(datetime(2026, 1, 2),
                                                  datetime(2026, 1, 3)))
        assert res['has_conflicts'] is False
        # exception
        with patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError('x'))):
            res = asyncio.run(svc.check_conflicts(datetime(2026, 1, 1),
                                                  datetime(2026, 1, 2)))
        assert res['success'] is False
        # unauthenticated
        svc2 = GoogleCalendarService(tenant_id='t', config={})
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=False):
            res = asyncio.run(svc2.check_conflicts(datetime(2026, 1, 1),
                                                   datetime(2026, 1, 2)))
        assert 'error' in res

    def test_conversions_and_parse_time(self):
        svc = _google_service()
        uni = svc._convert_google_to_unified(_google_event())
        assert uni['attendees'] == ['a@b.c']
        g = svc._convert_unified_to_google({'title': 'T', 'location': 'L',
                                            'attendees': ['a@b.c'],
                                            'start_time': 's',
                                            'end_time': 'e'})
        assert g['location'] == 'L'
        g2 = svc._convert_unified_to_google({})
        assert 'location' not in g2
        assert svc._parse_event_time('2026-01-01').hour == 0
        assert svc._parse_event_time('2026-01-01T09:30:00Z').tzinfo is not None

    def test_sync_to_postgres_cache(self):
        svc = _google_service()
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        with patch('core.database.SessionLocal', return_value=db), \
             patch('core.models.IntegrationMetric', MagicMock()), \
             patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(return_value=[{}])):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is True
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
        db.commit.side_effect = RuntimeError('db')
        with patch('core.database.SessionLocal', return_value=db), \
             patch('core.models.IntegrationMetric', MagicMock()), \
             patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError())):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is False
        with patch('core.database.SessionLocal',
                   side_effect=RuntimeError('nope')), \
             patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(return_value=[])):
            res = asyncio.run(svc.sync_to_postgres_cache('ws1'))
        assert res['success'] is False

    def test_full_sync_and_meta(self):
        svc = _google_service()
        with patch.object(GoogleCalendarService, 'sync_to_postgres_cache',
                          AsyncMock(return_value={'success': True})):
            res = asyncio.run(svc.full_sync('ws1'))
        assert res['success'] is True
        assert 'get_events' in svc.get_capabilities()['operations']
        with patch.object(GoogleCalendarService, 'authenticate',
                          return_value=True):
            assert svc.health_check()['status'] == 'healthy'
        with patch.object(GoogleCalendarService, 'authenticate',
                          side_effect=RuntimeError('x')):
            assert svc.health_check()['status'] == 'unhealthy'

    def test_execute_operation(self):
        svc = _google_service()
        res = asyncio.run(svc.execute_operation(
            'get_events', {}, context={'tenant_id': 'other'}))
        assert res['success'] is False
        ev = {'id': 'g'}
        with patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(return_value=[ev])):
            res = asyncio.run(svc.execute_operation('get_events', {}))
        assert res['data'] == [ev]
        with patch.object(GoogleCalendarService, 'create_event',
                          AsyncMock(return_value=ev)):
            res = asyncio.run(svc.execute_operation(
                'create_event', {'event_data': {}, 'token': 't'}))
        assert res['success'] is True
        with patch.object(GoogleCalendarService, 'create_event',
                          AsyncMock(return_value=None)):
            res = asyncio.run(svc.execute_operation(
                'create_event', {'event_data': {}}))
        assert res['success'] is False
        with patch.object(GoogleCalendarService, 'update_event',
                          AsyncMock(return_value=ev)):
            res = asyncio.run(svc.execute_operation(
                'update_event', {'event_id': 'g', 'updates': {}}))
        assert res['success'] is True
        with patch.object(GoogleCalendarService, 'update_event',
                          AsyncMock(return_value=None)):
            res = asyncio.run(svc.execute_operation(
                'update_event', {'event_id': 'g'}))
        assert res['success'] is False
        with patch.object(GoogleCalendarService, 'delete_event',
                          AsyncMock(return_value=True)):
            res = asyncio.run(svc.execute_operation(
                'delete_event', {'event_id': 'g'}))
        assert res['success'] is True
        with patch.object(GoogleCalendarService, 'check_conflicts',
                          AsyncMock(return_value={'has_conflicts': False})):
            res = asyncio.run(svc.execute_operation(
                'check_conflicts',
                {'start_time': datetime(2026, 1, 1),
                 'end_time': datetime(2026, 1, 2)}))
        assert res['success'] is True
        assert asyncio.run(svc.execute_operation('bogus', {}))['success'] is False
        with patch.object(GoogleCalendarService, 'get_events',
                          AsyncMock(side_effect=RuntimeError('x'))):
            res = asyncio.run(svc.execute_operation('get_events', {}))
        assert res['success'] is False

    def test_singleton(self):
        assert gcal_mod.google_calendar_service is not None
