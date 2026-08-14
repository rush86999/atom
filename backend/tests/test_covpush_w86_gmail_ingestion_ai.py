# -*- coding: utf-8 -*-
"""Coverage wave 86 — integrations.gmail_service,
integrations.atom_communication_ingestion_pipeline,
integrations.atom_ai_integration.

No network, no LLM spend: Google API clients, aiohttp/httpx sessions,
LanceDB, IMAP, Slack SDK and LLM services are all mocked.
"""
import asyncio
import base64
import email as email_lib
import json
import os
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

import integrations.gmail_service as gsvc_mod
from integrations.gmail_service import GmailService, get_gmail_service
import integrations.atom_communication_ingestion_pipeline as pipe_mod
from integrations.atom_communication_ingestion_pipeline import (
    CommunicationAppType,
    CommunicationData,
    CommunicationIngestionPipeline,
    IngestionConfig,
    LanceDBMemoryManager,
)
import integrations.atom_ai_integration as ai_mod
from integrations.atom_ai_integration import (
    AIConversationManager,
    AtomAIIntegration,
    CrossPlatformAIManager,
    IntelligentSearchManager,
    WorkflowIntelligenceManager,
    _chat_completion_text,
    _messages_with_system,
)


def b64(s):
    return base64.urlsafe_b64encode(s.encode()).decode()


# ============================================================================
# GmailService — helpers
# ============================================================================

NONEXISTENT = {'credentials_path': '/nonexistent/creds.json',
               'token_path': '/nonexistent/token.json'}


@pytest.fixture()
def gmail():
    svc = GmailService(tenant_id='t1', config=dict(NONEXISTENT))
    svc.service = MagicMock()
    return svc


def test_gmail_capabilities_and_operations(gmail):
    caps = gmail.get_capabilities()
    assert caps['supports_webhooks'] is True
    assert len(gmail.get_operations()) == 2


def test_gmail_health_check(gmail):
    gmail.service = None
    assert gmail.health_check()['healthy'] is False
    gmail.service = MagicMock()
    gmail.service.users().getProfile.return_value.execute.return_value = {
        'emailAddress': 'a@b.c'}
    assert gmail.health_check()['healthy'] is True
    gmail.service.users().getProfile.side_effect = RuntimeError('x')
    assert gmail.health_check()['healthy'] is False


def test_gmail_test_connection(gmail):
    gmail.service = None
    assert gmail.test_connection()['status'] == 'error'
    gmail.service = MagicMock()
    gmail.service.users().getProfile.return_value.execute.return_value = {
        'emailAddress': 'a@b.c', 'messagesTotal': 5, 'threadsTotal': 2,
        'historyId': '1'}
    res = gmail.test_connection()
    assert res['status'] == 'success' and res['email'] == 'a@b.c'
    gmail.service.users().getProfile.side_effect = RuntimeError('x')
    assert gmail.test_connection()['status'] == 'error'


# ============================================================================
# GmailService — _authenticate branches
# ============================================================================

def _creds(valid=True, expired=False, refresh_token='r'):
    c = MagicMock()
    c.valid = valid
    c.expired = expired
    c.refresh_token = refresh_token
    c.token = 'tok'
    c.token_uri = 'uri'
    c.client_id = 'cid'
    c.client_secret = 'sec'
    c.scopes = ['s']
    c.to_json.return_value = '{}'
    return c


def test_authenticate_stored_valid_token():
    svc = GmailService(tenant_id='t', config=dict(NONEXISTENT))
    creds = _creds()
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'Credentials', return_value=creds) as CC, \
            patch.object(gsvc_mod, 'build', return_value=MagicMock()) as b:
        ts.get_token.return_value = {'access_token': 'a', 'refresh_token': 'r'}
        svc._authenticate()
    assert svc.service is b.return_value
    CC.assert_called_once()


def test_authenticate_refresh_expired_stored_token(tmp_path):
    token_file = tmp_path / 'token.json'
    svc = GmailService(tenant_id='t', config={
        'credentials_path': '/nonexistent/creds.json',
        'token_path': str(token_file)})
    creds = _creds(valid=False, expired=True)
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'Credentials', return_value=creds), \
            patch.object(gsvc_mod, 'Request'), \
            patch.object(gsvc_mod, 'build', return_value=MagicMock()):
        ts.get_token.return_value = {'access_token': 'a', 'refresh_token': 'r'}
        svc._authenticate()
    ts.save_token.assert_called_once()


def test_authenticate_from_token_file(tmp_path):
    token_file = tmp_path / 'token.json'
    token_file.write_text('{}')
    svc = GmailService(tenant_id='t', config={
        'credentials_path': '/nonexistent/creds.json',
        'token_path': str(token_file)})
    creds = _creds()
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'Credentials') as CC, \
            patch.object(gsvc_mod, 'build', return_value=MagicMock()):
        ts.get_token.return_value = None
        CC.from_authorized_user_file.return_value = creds
        svc._authenticate()
    CC.from_authorized_user_file.assert_called_once()
    # token file re-saved
    assert token_file.read_text() == '{}'


def test_authenticate_flow_raises_auth_url(tmp_path):
    cred_file = tmp_path / 'creds.json'
    cred_file.write_text('{}')
    svc = GmailService(tenant_id='t', config={
        'credentials_path': str(cred_file),
        'token_path': str(tmp_path / 'none.json')})
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'Flow') as Flow, \
            patch.object(gsvc_mod, 'build') as b:
        ts.get_token.return_value = None
        flow = MagicMock()
        Flow.from_client_secrets_file.return_value = flow
        flow.authorization_url.return_value = ('http://auth', 'state')
        svc._authenticate()
    assert svc.service is None


def test_authenticate_oauth_configured_no_token(tmp_path):
    svc = GmailService(tenant_id='t', config={
        'credentials_path': str(tmp_path / 'nope.json'),
        'token_path': str(tmp_path / 'nope2.json')})
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'GOOGLE_OAUTH_CONFIG') as cfg, \
            patch.object(gsvc_mod, 'build') as b:
        ts.get_token.return_value = None
        cfg.is_configured.return_value = True
        svc._authenticate()
    assert svc.service is b.return_value  # build called with creds=None


def test_authenticate_not_configured_raises(tmp_path):
    svc = GmailService(tenant_id='t', config={
        'credentials_path': str(tmp_path / 'nope.json'),
        'token_path': str(tmp_path / 'nope2.json')})
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'GOOGLE_OAUTH_CONFIG') as cfg:
        ts.get_token.return_value = None
        cfg.is_configured.return_value = False
        svc._authenticate()  # swallowed, service None
    assert svc.service is None


def test_authenticate_unexpected_exception():
    svc = GmailService(tenant_id='t', config=dict(NONEXISTENT))
    with patch.object(gsvc_mod, 'token_storage') as ts:
        ts.get_token.side_effect = RuntimeError('boom')
        svc._authenticate()
    assert svc.service is None


def test_get_service_with_token(gmail):
    assert gmail._get_service_with_token(None) is gmail.service
    with patch.object(gsvc_mod, 'Credentials', return_value=MagicMock()), \
            patch.object(gsvc_mod, 'build', return_value='built'):
        assert gmail._get_service_with_token('tok') == 'built'
    with patch.object(gsvc_mod, 'Credentials', side_effect=RuntimeError('x')):
        assert gmail._get_service_with_token('tok') is None


def test_get_calendar_service(gmail):
    with patch.object(gsvc_mod, 'Credentials', return_value=MagicMock()), \
            patch.object(gsvc_mod, 'build', return_value='cal'):
        assert gmail._get_calendar_service('tok') == 'cal'
    with patch.object(gsvc_mod, 'token_storage') as ts, \
            patch.object(gsvc_mod, 'Credentials', return_value=MagicMock()), \
            patch.object(gsvc_mod, 'build', return_value='cal2'):
        ts.get_token.return_value = {'access_token': 'a'}
        assert gmail._get_calendar_service(None) == 'cal2'
    with patch.object(gsvc_mod, 'token_storage') as ts:
        ts.get_token.return_value = None
        assert gmail._get_calendar_service(None) is None
    with patch.object(gsvc_mod, 'token_storage') as ts:
        ts.get_token.side_effect = RuntimeError('x')
        assert gmail._get_calendar_service(None) is None


# ============================================================================
# GmailService — message operations
# ============================================================================

def _full_msg(mid='m1'):
    return {
        'id': mid, 'threadId': 't1', 'snippet': 'snip',
        'labelIds': ['INBOX'], 'historyId': 'h', 'internalDate': '123',
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Hi'},
                {'name': 'From', 'value': 'a@b.c'},
                {'name': 'Date', 'value': '2026-01-01'},
            ],
            'body': {'data': b64('hello body')},
        },
    }


def test_get_message_and_parse(gmail):
    gmail.service.users().messages.return_value.get.return_value.execute \
        .return_value = _full_msg()
    msg = gmail.get_message('m1')
    assert msg['subject'] == 'Hi' and msg['body'] == 'hello body'
    assert msg['attachments'] == []

    gmail.service = None
    assert gmail.get_message('m1') is None


def test_get_message_error(gmail):
    gmail.service.users().messages.side_effect = RuntimeError('x')
    assert gmail.get_message('m1') is None


def test_parse_message_bad_payload(gmail):
    assert gmail._parse_message({'id': 'x'}) == {}


def test_extract_body_variants(gmail):
    assert gmail._extract_body({'body': {'data': b64('top')}}) == 'top'
    assert gmail._extract_body({'parts': [
        {'mimeType': 'text/plain', 'body': {'data': b64('plain')}}]}) == 'plain'
    assert gmail._extract_body({'parts': [
        {'mimeType': 'text/html', 'body': {'data': b64('<b>h</b>')}}]}) == '<b>h</b>'
    assert gmail._extract_body({'parts': [
        {'mimeType': 'other'},
        {'mimeType': 'multipart/alternative',
         'parts': [{'mimeType': 'text/plain', 'body': {'data': b64('nested')}}]}]}) == 'nested'
    assert gmail._extract_body({'parts': [{'mimeType': 'text/plain'}]}) == ''
    assert gmail._extract_body({'body': {'data': '!!!not-base64###'}}) == ''


def test_extract_attachments(gmail):
    payload = {'parts': [
        {'filename': 'a.pdf', 'mimeType': 'application/pdf',
         'body': {'attachmentId': 'att1', 'size': 10}},
        {'parts': [{'filename': 'b.txt', 'mimeType': 'text/plain',
                    'body': {'attachmentId': 'att2'}}]},
    ]}
    atts = gmail._extract_attachments(payload)
    assert [a['attachmentId'] for a in atts] == ['att1', 'att2']
    # exception branch -> empty
    bad = {'parts': None}
    bad['parts'] = None
    assert gmail._extract_attachments({'parts': [None]}) == []


def test_get_messages_pagination(gmail):
    list_exec = gmail.service.users().messages.return_value.list
    list_exec.return_value.execute.side_effect = [
        {'messages': [{'id': 'm1'}], 'nextPageToken': 'p2'},
        {'messages': [{'id': 'm2'}]},
    ]
    gmail.get_message = MagicMock(side_effect=lambda mid, token=None: {'id': mid})
    msgs = gmail.get_messages('q', max_results=10)
    assert [m['id'] for m in msgs] == ['m1', 'm2']


def _http_err():
    import httplib2
    return gsvc_mod.HttpError(httplib2.Response({'status': '500'}), b'err')


def test_get_messages_http_error_and_no_service():
    svc = GmailService(tenant_id='t', config=dict(NONEXISTENT))
    assert svc.get_messages() == []
    svc.service = MagicMock()
    svc.service.users().messages.return_value.list.return_value.execute \
        .side_effect = _http_err()
    svc.get_message = MagicMock(return_value=None)
    assert svc.get_messages() == []


def test_get_attachment_content(gmail):
    gmail.service.users().messages.return_value.attachments.return_value.get \
        .return_value.execute.return_value = {'data': b64('bytes')}
    assert gmail.get_attachment_content('m', 'a') == b'bytes'
    gmail.service.users().messages.return_value.attachments.return_value.get \
        .return_value.execute.return_value = {}
    assert gmail.get_attachment_content('m', 'a') is None
    gmail.service = None
    assert gmail.get_attachment_content('m', 'a') is None


def test_send_message(gmail):
    send_exec = gmail.service.users().messages.return_value.send \
        .return_value.execute
    send_exec.return_value = {'id': 'sent'}
    assert gmail.send_message('x@y.z', 'S', 'B', cc='c@d.e', bcc='e@f.g',
                              thread_id='t1') == {'id': 'sent'}
    assert gmail.send_message('x@y.z', 'S', 'B') == {'id': 'sent'}
    gmail.service = None
    assert gmail.send_message('x@y.z', 'S', 'B') is None
    gmail.service = MagicMock()
    gmail.service.users.side_effect = RuntimeError('x')
    assert gmail.send_message('x@y.z', 'S', 'B') is None


def _thread_payload():
    return {'messages': [{'payload': {'headers': [
        {'name': 'Message-ID', 'value': '<1>'},
        {'name': 'Reply-To', 'value': 'r@b.c'},
        {'name': 'Subject', 'value': 'Hello'},
    ]}}]}


def test_reply_to_message(gmail):
    gmail.service.users().threads.return_value.get.return_value.execute \
        .return_value = _thread_payload()
    send_exec = gmail.service.users().messages.return_value.send \
        .return_value.execute
    send_exec.return_value = {'id': 're'}
    assert gmail.reply_to_message('t1', 'hi back') == {'id': 're'}

    # no reply-to header -> falls back to From
    gmail.service.users().threads.return_value.get.return_value.execute \
        .return_value = {'messages': [{'payload': {'headers': [
            {'name': 'From', 'value': 'f@b.c'},
            {'name': 'Subject', 'value': 'Re: already'},
        ]}}]}
    assert gmail.reply_to_message('t1', 'x') == {'id': 're'}

    gmail.service.users().threads.return_value.get.return_value.execute \
        .return_value = {'messages': []}
    assert gmail.reply_to_message('t1', 'x') is None
    gmail.service = None
    assert gmail.reply_to_message('t1', 'x') is None
    gmail.service = MagicMock()
    gmail.service.users.side_effect = RuntimeError('x')
    assert gmail.reply_to_message('t1', 'x') is None


def test_draft_message(gmail):
    drafts_exec = gmail.service.users().drafts.return_value.create \
        .return_value.execute
    drafts_exec.return_value = {'id': 'd1'}
    assert gmail.draft_message('x@y.z', 'S', 'B', thread_id='t') == {'id': 'd1'}
    gmail.service = None
    assert gmail.draft_message('x@y.z', 'S', 'B') is None
    gmail.service = MagicMock()
    gmail.service.users.side_effect = RuntimeError('x')
    assert gmail.draft_message('x@y.z', 'S', 'B') is None


def test_search_messages(gmail):
    gmail.get_messages = MagicMock(return_value=[{'id': 'm'}])
    assert gmail.search_messages('q', 5) == [{'id': 'm'}]


def test_get_threads(gmail):
    lst = gmail.service.users().threads.return_value.list
    lst.return_value.execute.side_effect = [
        {'threads': [{'id': 't1'}], 'nextPageToken': 'p'},
        {'threads': [{'id': 't2'}]},
    ]
    get_exec = gmail.service.users().threads.return_value.get \
        .return_value.execute
    get_exec.side_effect = [{'id': 't1'}, RuntimeError('x')]
    threads = gmail.get_threads(max_results=5)
    assert threads == [{'id': 't1'}]

    lst.return_value.execute.side_effect = _http_err()
    assert gmail.get_threads() == []
    gmail.service.users.side_effect = RuntimeError('x')
    assert gmail.get_threads() == []


def test_modify_delete_message(gmail):
    assert gmail.modify_message('m', add_labels=['X'], remove_labels=['Y']) is True
    assert gmail.modify_message('m') is True
    gmail.service.users.side_effect = RuntimeError('x')
    assert gmail.modify_message('m') is False
    assert gmail.delete_message('m') is False
    gmail.service = MagicMock()
    assert gmail.delete_message('m') is True


def test_labels(gmail):
    gmail.service.users().labels.return_value.list.return_value.execute \
        .return_value = {'labels': [{'id': 'L1'}]}
    assert gmail.get_labels() == [{'id': 'L1'}]
    gmail.service.users().labels.return_value.create.return_value.execute \
        .return_value = {'id': 'L2'}
    assert gmail.create_label('New', color={'bg': '#fff'}) == {'id': 'L2'}

    svc = GmailService(tenant_id='t', config=dict(NONEXISTENT))
    assert svc.get_labels() == []
    svc.service = MagicMock()
    svc.service.users.side_effect = RuntimeError('x')
    assert svc.get_labels() == []
    assert svc.create_label('N') is None


async def test_sync_to_postgres_cache(gmail, monkeypatch):
    gmail.service = None
    assert (await gmail.sync_to_postgres_cache())['success'] is False

    gmail.service = MagicMock()
    gmail.service.users().getProfile.return_value.execute.return_value = {
        'messagesTotal': 10, 'threadsTotal': 5}
    gmail.service.users().messages.return_value.list.return_value.execute \
        .return_value = {'resultSizeEstimate': 2}
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db))
    res = await gmail.sync_to_postgres_cache('me')
    assert res == {'success': True, 'metrics_synced': 3}

    # update-existing path
    db.query.return_value.filter_by.return_value.first.return_value = MagicMock()
    assert (await gmail.sync_to_postgres_cache('me'))['success'] is True

    # commit failure
    db.commit = MagicMock(side_effect=RuntimeError('x'))
    assert (await gmail.sync_to_postgres_cache('me'))['success'] is False

    # outer exception
    gmail.service.users.side_effect = RuntimeError('x')
    assert (await gmail.sync_to_postgres_cache('me'))['success'] is False


async def test_full_sync(gmail):
    gmail.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 1})
    res = await gmail.full_sync('me')
    assert res['success'] is True and res['postgres_cache']['metrics_synced'] == 1


async def test_sync_calendar_events(gmail, monkeypatch):
    gmail._get_calendar_service = MagicMock(return_value=None)
    await gmail.sync_calendar_events('u')  # no service branch

    cal = MagicMock()
    cal.events.return_value.list.return_value.execute.return_value = {
        'items': [{
            'id': 'e1', 'summary': 'Meeting', 'description': 'd',
            'organizer': {'email': 'o@b.c'}, 'start': {'dateTime': 's'},
            'end': {'date': '2026-01-01'}, 'attendees': [], 'status': 'confirmed',
        }]}
    gmail._get_calendar_service = MagicMock(return_value=cal)
    pipeline = MagicMock()
    pipeline.ingest_message = AsyncMock(side_effect=RuntimeError('x'))
    monkeypatch.setattr(
        'integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline',
        lambda: pipeline)
    await gmail.sync_calendar_events('u')  # ingest error logged, not raised

    cal.events.return_value.list.return_value.execute.side_effect = RuntimeError('x')
    await gmail.sync_calendar_events('u')


def test_calendar_crud(gmail):
    gmail._get_calendar_service = MagicMock(return_value=None)
    assert gmail.create_calendar_event({}) is None
    assert gmail.update_calendar_event('e', {}) is None
    cal = MagicMock()
    gmail._get_calendar_service = MagicMock(return_value=cal)
    gmail.create_calendar_event({})
    gmail.update_calendar_event('e', {})
    gmail._get_calendar_service = MagicMock(side_effect=RuntimeError('x'))
    assert gmail.create_calendar_event({}) is None
    assert gmail.update_calendar_event('e', {}) is None


async def test_execute_operation_dispatch(gmail):
    gmail.send_message = MagicMock(return_value={'id': 's'})
    assert (await gmail.execute_operation('send_email', {
        'to': 'a@b.c', 'subject': 's', 'body': 'b'}))['success'] is True
    gmail.get_messages = MagicMock(return_value=[{'id': 'm'}])
    assert (await gmail.execute_operation('list_messages', {}))['success'] is True
    gmail.get_message = MagicMock(return_value={'id': 'm'})
    assert (await gmail.execute_operation('get_message', {'message_id': 'm'}))['success'] is True
    gmail.search_messages = MagicMock(return_value=[])
    assert (await gmail.execute_operation('search_messages', {'query': 'q'}))['success'] is True
    gmail.reply_to_message = MagicMock(return_value={'id': 'r'})
    assert (await gmail.execute_operation('reply_to_message', {
        'thread_id': 't', 'body': 'b'}))['success'] is True
    gmail.draft_message = MagicMock(return_value={'id': 'd'})
    assert (await gmail.execute_operation('draft_message', {
        'to': 'a@b.c', 'subject': 's', 'body': 'b'}))['success'] is True
    gmail.modify_message = MagicMock(return_value=True)
    assert (await gmail.execute_operation('modify_message', {
        'message_id': 'm'}))['success'] is True
    gmail.delete_message = MagicMock(return_value=True)
    assert (await gmail.execute_operation('delete_message', {
        'message_id': 'm'}))['success'] is True
    gmail.sync_calendar_events = AsyncMock()
    assert (await gmail.execute_operation('sync_calendar', {}))['success'] is True
    assert (await gmail.execute_operation('bogus', {}))['success'] is False


async def test_execute_operation_tenant_mismatch(gmail):
    res = await gmail.execute_operation(
        'send_email', {}, context={'tenant_id': 'other'})
    assert res['success'] is False and res['error'] == 'Tenant ID mismatch'


@pytest.mark.parametrize('exc,code', [
    ('invalid credentials', 'AUTH_INVALID'),
    ('rate limit exceeded', 'RATE_LIMIT'),
    ('resource not found', 'RESOURCE_NOT_FOUND'),
    ('permission forbidden 403', 'PERMISSION_DENIED'),
    ('mystery failure', 'UNKNOWN'),
])
async def test_execute_operation_error_codes(gmail, exc, code):
    gmail.get_messages = MagicMock(side_effect=RuntimeError(exc))
    res = await gmail.execute_operation('list_messages', {})
    assert res['success'] is False and res['error'] == code


async def test_fetch_recent_messages(gmail, monkeypatch):
    gmail.get_messages = MagicMock(
        return_value=[{'id': 'm1'}, {'id': 'm2'}])
    pipeline = MagicMock()
    pipeline.ingest_message = AsyncMock(return_value=True)
    monkeypatch.setattr(
        'integrations.atom_communication_ingestion_pipeline.get_ingestion_pipeline',
        lambda: pipeline)
    msgs = await gmail.fetch_recent_messages('u', token='tok')
    assert len(msgs) == 2 and pipeline.ingest_message.await_count == 2

    gmail.get_messages = MagicMock(side_effect=RuntimeError('x'))
    assert await gmail.fetch_recent_messages('u') == []


async def test_attachment_metadata_and_download(gmail):
    gmail.get_message = MagicMock(return_value=None)
    assert await gmail.get_attachment_metadata('u', 'm') == []
    gmail.get_message = MagicMock(return_value={'attachments': [{
        'attachmentId': 'a1', 'filename': 'f.pdf', 'size': 5,
        'mimeType': 'application/pdf'}]})
    meta = await gmail.get_attachment_metadata('u', 'm')
    assert meta[0]['id'] == 'a1' and meta[0]['contentType'] == 'application/pdf'
    gmail.get_attachment_content = MagicMock(return_value=b'data')
    assert await gmail.download_attachment('u', 'm', 'a1') == b'data'


def test_get_gmail_service_factory():
    svc = get_gmail_service('t', dict(NONEXISTENT))
    assert svc.tenant_id == 't'


# ============================================================================
# Ingestion pipeline — fixtures
# ============================================================================

@pytest.fixture()
def mm():
    mgr = LanceDBMemoryManager(db_path='/tmp/atom_test_mm', workspace_id='w1')
    mgr.db = MagicMock()
    mgr.connections_table = MagicMock()
    mgr.metadata_table = MagicMock()
    return mgr


@pytest.fixture()
def pipe(mm):
    p = CommunicationIngestionPipeline(mm)
    p.webhook_processor = None
    return p


def _cfg(app, **kw):
    d = dict(enabled=True, real_time=False, batch_size=10,
             ingest_attachments=True, embed_content=False, retention_days=30)
    d.update(kw)
    return IngestionConfig(app_type=app, enabled=d['enabled'],
                           real_time=d['real_time'], batch_size=d['batch_size'],
                           ingest_attachments=d['ingest_attachments'],
                           embed_content=d['embed_content'],
                           retention_days=d['retention_days'])


def _comm(cid='c1'):
    return CommunicationData(
        id=cid, app_type='whatsapp', timestamp=datetime.now(timezone.utc),
        direction='inbound', sender='s', recipient='r', subject='sub',
        content='hello', attachments=[], metadata={}, status='active',
        priority='normal', tags=['t'])


# ============================================================================
# LanceDBMemoryManager
# ============================================================================

def test_mm_initialize(mm):
    with patch.object(pipe_mod, 'lancedb') as ldb, \
            patch.object(pipe_mod, '_get_sentence_transformer', return_value=None), \
            patch.object(mm, '_create_connections_table'), \
            patch.object(mm, '_create_metadata_table'):
        mm.db = None
        ldb.connect.return_value = 'db'
        assert mm.initialize() is True

        ldb.connect.side_effect = RuntimeError('x')
        assert mm.initialize() is False


def test_mm_initialize_with_model(mm):
    st = MagicMock()
    with patch.object(pipe_mod, 'lancedb') as ldb, \
            patch.object(pipe_mod, '_get_sentence_transformer', return_value=st):
        ldb.connect.return_value = 'db'
        with patch.object(mm, '_create_connections_table'), \
                patch.object(mm, '_create_metadata_table'):
            assert mm.initialize() is True
        st.assert_called_with('all-mpnet-base-v2')

        # model load failure -> continues without embeddings
        st.side_effect = RuntimeError('x')
        with patch.object(mm, '_create_connections_table'), \
                patch.object(mm, '_create_metadata_table'):
            assert mm.initialize() is True


def test_mm_create_tables(mm):
    db = MagicMock()
    db.table_names.return_value = []
    mm.db = db
    mm._create_connections_table()
    db.create_table.assert_called_once()
    # second time opens existing; FTS failure tolerated
    db.table_names.return_value = ['atom_communications', 'ingestion_metadata']
    mm._create_connections_table()
    mm._create_metadata_table()
    db.open_table.assert_any_call('atom_communications')
    db.open_table.assert_any_call('ingestion_metadata')


def test_mm_ingest_communication(mm):
    assert mm.ingest_communication(_comm()) is True
    mm.connections_table.add.side_effect = RuntimeError('x')
    assert mm.ingest_communication(_comm()) is False


def test_mm_ingest_generic_record(mm):
    rec = MagicMock()
    rec.id = 'r1'
    rec.app_type = 'crm_lead'
    rec.timestamp = datetime.now(timezone.utc)
    rec.record_type.value = 'lead'
    rec.content = 'content'
    rec.metadata = {'a': 1}
    rec.vector_embedding = None
    assert mm.ingest_generic_record(rec) is True
    rec.vector_embedding = [0.1] * 4
    assert mm.ingest_generic_record(rec) is True
    mm.connections_table.add.side_effect = RuntimeError('x')
    assert mm.ingest_generic_record(rec) is False


def test_mm_ingest_batch(mm):
    assert mm.ingest_batch([_comm('a'), _comm('b')]) is True
    mm.connections_table.add.side_effect = RuntimeError('x')
    assert mm.ingest_batch([_comm('c')]) is False


def test_mm_generate_embedding(mm):
    assert mm.generate_embedding('x') == [0.0] * 768
    mm.model = MagicMock()
    mm.model.encode.return_value.tolist.return_value = [0.5]
    assert mm.generate_embedding('x') == [0.5]
    mm.model.encode.side_effect = RuntimeError('x')
    assert mm.generate_embedding('x') == [0.0] * 768


def _chain_mock(final):
    """Mock whose builder methods all return itself, terminating at `final`."""
    sb = MagicMock()
    for m in ('vector', 'text', 'limit', 'where'):
        getattr(sb, m).return_value = sb
    sb.to_pandas.return_value = final
    return sb


def test_mm_search_communications(mm):
    mm.generate_embedding = MagicMock(return_value=[0.0] * 768)
    sb = _chain_mock(pd.DataFrame([{'id': 'x'}]))
    mm.connections_table.search.return_value = sb
    assert mm.search_communications('q', app_type='slack', tag='t') == [{'id': 'x'}]

    # hybrid failure -> vector fallback
    def search_side(v=None, **kw):
        if v is None and kw.get('query_type') == 'hybrid':
            raise RuntimeError('no hybrid')
        return sb
    mm.connections_table.search = MagicMock(side_effect=search_side)
    assert mm.search_communications('q') == [{'id': 'x'}]

    mm.connections_table = None
    assert mm.search_communications('q') == []
    mm.connections_table = MagicMock()
    mm.connections_table.search.side_effect = RuntimeError('x')
    assert mm.search_communications('q') == []


def test_mm_get_by_app_and_timeframe(mm):
    mm.connections_table.search = MagicMock(
        return_value=_chain_mock(pd.DataFrame(
            [{'id': '1', 'timestamp': 2}, {'id': '2', 'timestamp': 1}])))
    rows = mm.get_communications_by_app('slack')
    assert rows[0]['id'] == '1'
    mm.connections_table.search = MagicMock(
        return_value=_chain_mock(pd.DataFrame()))
    assert mm.get_communications_by_app('slack') == []
    assert mm.get_communications_by_timeframe(
        datetime(2026, 1, 1), datetime(2026, 1, 2)) == []
    mm.connections_table.search = MagicMock(side_effect=RuntimeError('x'))
    assert mm.get_communications_by_app('slack') == []


def test_mm_update_metadata(mm):
    mm.metadata_table.search.return_value.where.return_value.to_pandas \
        .return_value = pd.DataFrame([{'total_messages': 5}])
    mm._update_metadata('slack', 2)
    mm.metadata_table.delete.assert_called_once()

    mm.metadata_table.search.return_value.where.return_value.to_pandas \
        .return_value = pd.DataFrame()
    mm._update_metadata('slack', 2)
    mm.metadata_table.add.assert_called()

    mm.metadata_table.search.side_effect = RuntimeError('x')
    mm._update_metadata('slack', 2)  # logged only


def test_get_memory_manager_factory():
    mgr = pipe_mod.get_memory_manager('factory_ws_test')
    assert pipe_mod.get_memory_manager('factory_ws_test') is mgr
    assert pipe_mod.get_ingestion_pipeline('factory_ws_test').memory_manager is mgr


# ============================================================================
# CommunicationIngestionPipeline — config & webhooks
# ============================================================================

def test_configure_and_webhooks(pipe):
    pipe.configure_app(CommunicationAppType.SLACK, _cfg(CommunicationAppType.SLACK))
    assert 'slack' in pipe.ingestion_configs
    pipe.enable_webhook_ingestion('slack', True)
    assert pipe.is_webhook_enabled('slack') is True
    assert pipe.is_webhook_enabled('teams') is False
    status = pipe.get_webhook_status()
    assert set(status) == {'slack', 'teams', 'gmail', 'outlook'}
    assert status['slack']['enabled'] is True


async def test_handle_webhook_message(pipe):
    await pipe._handle_webhook_message({})  # missing app_type
    await pipe._handle_webhook_message({'app_type': 'slack'})  # disabled
    pipe.enable_webhook_ingestion('slack', True)
    pipe.ingest_message = AsyncMock(return_value=True)
    await pipe._handle_webhook_message({'app_type': 'slack', 'id': 'm'})
    pipe.ingest_message = AsyncMock(return_value=False)
    await pipe._handle_webhook_message({'app_type': 'slack'})
    pipe.ingest_message = AsyncMock(side_effect=RuntimeError('x'))
    await pipe._handle_webhook_message({'app_type': 'slack'})


# ============================================================================
# CommunicationIngestionPipeline — ingest_message
# ============================================================================

def _settings(auto=True, extract=True):
    s = MagicMock()
    s.is_automations_enabled.return_value = auto
    s.is_extraction_enabled.return_value = extract
    return s


async def test_ingest_message_basic(pipe):
    pipe.memory_manager.db = MagicMock()
    pipe.memory_manager.ingest_communication = MagicMock(return_value=True)
    with patch('core.automation_settings.get_automation_settings',
               return_value=_settings(auto=False)):
        assert await pipe.ingest_message('whatsapp', {
            'id': 'w1', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'from': 's', 'to': 'r', 'content': 'hi'}) is True


async def test_ingest_message_initializes_db(pipe):
    pipe.memory_manager.db = None
    pipe.memory_manager.initialize = MagicMock(return_value=True)
    pipe.memory_manager.ingest_communication = MagicMock(return_value=True)
    with patch('core.automation_settings.get_automation_settings',
               return_value=_settings(auto=False)):
        assert await pipe.ingest_message('slack', {'id': 's1'}) is True
    pipe.memory_manager.initialize.assert_called_once()


async def test_ingest_message_with_embedding_and_extraction(pipe):
    pipe.memory_manager.db = MagicMock()
    pipe.memory_manager.ingest_communication = MagicMock(return_value=True)
    pipe.configure_app(CommunicationAppType.SLACK,
                       _cfg(CommunicationAppType.SLACK, embed_content=True))
    pipe.memory_manager.generate_embedding = MagicMock(return_value=[0.1])
    ki = MagicMock()
    ki.process_document = AsyncMock()
    intel = MagicMock()
    intel.analyze_and_route = AsyncMock()
    with patch('core.automation_settings.get_automation_settings',
               return_value=_settings()), \
            patch.object(pipe_mod, 'get_knowledge_ingestion', return_value=ki), \
            patch('core.communication_intelligence.CommunicationIntelligenceService',
                  return_value=intel):
        ok = await pipe.ingest_message('slack', {
            'id': 's2', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'content': 'a' * 50, 'metadata': {'user_id': 'u'}})
    assert ok is True
    await asyncio.sleep(0)  # let create_task fire
    ki.process_document.assert_awaited()

    # extraction raising is swallowed
    with patch('core.automation_settings.get_automation_settings',
               return_value=_settings()), \
            patch.object(pipe_mod, 'get_knowledge_ingestion',
                         side_effect=RuntimeError('x')):
        assert await pipe.ingest_message('slack', {
            'id': 's3', 'content': 'b' * 50}) is True


async def test_ingest_message_failure_and_exception(pipe):
    pipe.memory_manager.db = MagicMock()
    pipe.memory_manager.ingest_communication = MagicMock(return_value=False)
    assert await pipe.ingest_message('slack', {'id': 'x'}) is False
    pipe._normalize_message = MagicMock(side_effect=RuntimeError('x'))
    assert await pipe.ingest_message('slack', {'id': 'x'}) is False


def test_normalize_message_variants(pipe):
    wa = pipe._normalize_message('whatsapp', {
        'id': 'w', 'timestamp': datetime.now(timezone.utc).isoformat(),
        'from': 'f', 'to': 't', 'content': 'c'})
    assert wa['app_type'] == 'whatsapp' and wa['priority'] == 'normal'
    wa_def = pipe._normalize_message('whatsapp', {})
    assert wa_def['id'].startswith('wa_')

    em = pipe._normalize_message('email', {
        'id': 'e', 'date': datetime.now(timezone.utc).isoformat(),
        'from': 'user', 'body': 'b'})
    assert em['direction'] == 'outbound'
    gen = pipe._normalize_message('slack', {'content': 'x'})
    assert gen['id'].startswith('slack_')


def test_generate_embedding_delegates(pipe):
    pipe.memory_manager.generate_embedding = MagicMock(return_value=[1])
    assert pipe._generate_embedding('t') == [1]


def test_get_ingestion_stats(pipe):
    pipe.memory_manager.metadata_table.search.return_value.to_pandas \
        .return_value = pd.DataFrame([
            {'app_type': 'slack', 'total_messages': 5,
             'last_ingested': 'x', 'status': 'active'}])
    stats = pipe.get_ingestion_stats()
    assert stats['total_messages'] == 5
    pipe.memory_manager.metadata_table.search.side_effect = RuntimeError('x')
    assert 'error' in pipe.get_ingestion_stats()


# ============================================================================
# CommunicationIngestionPipeline — real-time stream
# ============================================================================

async def test_start_real_time_stream(pipe):
    assert pipe.start_real_time_stream('slack') is False  # unconfigured
    pipe.configure_app(CommunicationAppType.SLACK,
                       _cfg(CommunicationAppType.SLACK, real_time=False))
    assert pipe.start_real_time_stream('slack') is False
    pipe.configure_app(CommunicationAppType.SLACK,
                       _cfg(CommunicationAppType.SLACK, real_time=True))
    assert pipe.start_real_time_stream('slack') is True
    pipe.active_streams['slack'].cancel()


async def test_real_time_ingestion_loop(pipe):
    pipe.ingest_message = AsyncMock(return_value=True)
    pipe._fetch_new_messages = AsyncMock(side_effect=[[{'id': 'm'}], RuntimeError('x')])
    sleeps = []

    async def fake_sleep(secs):
        sleeps.append(secs)
        raise asyncio.CancelledError()

    with patch.object(pipe_mod.asyncio, 'sleep', side_effect=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await pipe._real_time_ingestion('slack')
    pipe.ingest_message.assert_awaited_once()

    # inner per-message failure is tolerated
    pipe.ingest_message = AsyncMock(side_effect=RuntimeError('x'))
    pipe._fetch_new_messages = AsyncMock(return_value=[{'id': 'm'}])
    with patch.object(pipe_mod.asyncio, 'sleep', side_effect=fake_sleep):
        with pytest.raises(asyncio.CancelledError):
            await pipe._real_time_ingestion('slack')


async def test_fetch_new_messages_dispatch(pipe, monkeypatch):
    for meth, app in (('_fetch_whatsapp_messages', 'whatsapp'),
                      ('_fetch_slack_messages', 'slack'),
                      ('_fetch_teams_messages', 'microsoft_teams'),
                      ('_fetch_email_messages', 'email'),
                      ('_fetch_gmail_messages', 'gmail'),
                      ('_fetch_outlook_messages', 'outlook')):
        m = AsyncMock(return_value=[{'id': 'x'}])
        monkeypatch.setattr(pipe, meth, m)
        assert await pipe._fetch_new_messages(app) == [{'id': 'x'}]
    assert await pipe._fetch_new_messages('notion') == []
    pipe.fetch_timestamps.clear()
    monkeypatch.setattr(pipe, '_fetch_slack_messages',
                        AsyncMock(side_effect=RuntimeError('x')))
    assert await pipe._fetch_new_messages('slack') == []
    assert 'last_fetch_slack' not in pipe.fetch_timestamps  # not updated on error


# ============================================================================
# Source connectors — whatsapp / slack / teams
# ============================================================================

async def test_fetch_whatsapp(pipe, monkeypatch):
    wa = MagicMock()
    wa.get_messages = AsyncMock(return_value=[{'id': 'w'}])
    monkeypatch.setattr(
        'integrations.atom_whatsapp_integration.atom_whatsapp_integration', wa)
    assert await pipe._fetch_whatsapp_messages(None) == [{'id': 'w'}]
    wa.get_messages = AsyncMock(side_effect=RuntimeError('x'))
    assert await pipe._fetch_whatsapp_messages(None) == []


def _slack_client(hist_responses=(), info=None, error=None):
    client = MagicMock()
    client.conversations_history = AsyncMock(side_effect=hist_responses or [])
    client.conversations_info = AsyncMock(return_value=info or {})
    client.close = AsyncMock()
    if error:
        client.conversations_history = AsyncMock(side_effect=error)
    return client


async def test_fetch_slack(pipe, monkeypatch):
    monkeypatch.delenv('SLACK_BOT_TOKEN', raising=False)
    assert await pipe._fetch_slack_messages(None) == []

    monkeypatch.setenv('SLACK_BOT_TOKEN', 'xoxb')
    pipe.app_configs['slack'] = {}
    assert await pipe._fetch_slack_messages(None) == []  # no channels

    pipe.app_configs['slack'] = {'monitored_channels': ['C1', 'C2']}
    info_resp = {'ok': True, 'channel': {'name': 'general'}}
    good = {'ok': True, 'messages': [
        {'ts': '100.1', 'type': 'message', 'text': 'hi', 'user': 'U1'},
        {'ts': '100.2', 'type': 'message', 'bot_id': 'B', 'text': 'bot'},
        {'ts': '100.3', 'type': 'message', 'subtype': 'message_changed'},
        {'ts': '100.4', 'type': 'message', 'subtype': 'message_deleted'},
        {'ts': '100.5', 'type': 'not_message'},
    ]}
    paged = {'ok': True, 'messages': [{'ts': '100.6', 'type': 'message',
                                       'text': 'p'}],
             'response_metadata': {'next_cursor': 'cur'}}
    done = {'ok': True, 'messages': []}
    client = _slack_client(hist_responses=[good, paged, done], info=info_resp)
    with patch('slack_sdk.web.async_client.AsyncWebClient',
               return_value=client):
        msgs = await pipe._fetch_slack_messages(datetime(2026, 1, 1))
    assert [m['id'] for m in msgs] == ['100.1', '100.6']  # sorted by ts
    client.close.assert_awaited_once()


async def test_fetch_slack_errors(pipe, monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'xoxb')
    pipe.app_configs['slack'] = {
        'monitored_channels': ['C1', 'C2', 'C3']}
    from slack_sdk.errors import SlackApiError
    rl = SlackApiError('rl', response={
        'data': {'error': 'ratelimited'}, 'headers': {'Retry-After': 1}})
    other = SlackApiError('e', response={'data': {'error': 'other'}})
    client = MagicMock()
    client.conversations_history = AsyncMock(side_effect=[rl, other, RuntimeError('x')])
    client.close = AsyncMock()
    with patch('slack_sdk.web.async_client.AsyncWebClient',
               return_value=client):
        assert await pipe._fetch_slack_messages(None) == []


async def test_get_channel_name(pipe):
    client = MagicMock()
    client.conversations_info = AsyncMock(
        return_value={'ok': True, 'channel': {'name': 'general'}})
    assert await pipe._get_channel_name(client, 'C1') == 'general'
    client.conversations_info = AsyncMock(side_effect=RuntimeError('x'))
    assert await pipe._get_channel_name(client, 'C1') is None


def _httpx_install(monkeypatch, get_responses):
    client = MagicMock()
    client.get = AsyncMock(side_effect=get_responses)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client)
    cm.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(pipe_mod.httpx, 'AsyncClient',
                        MagicMock(return_value=cm))
    return client


def _resp(status=200, payload=None, headers=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload or {}
    r.headers = headers or {}
    return r


async def test_fetch_teams_no_token(pipe, monkeypatch):
    with patch('core.token_storage.token_storage') as ts:
        ts.get_token.return_value = None
        assert await pipe._fetch_teams_messages(None) == []
        assert await pipe._fetch_outlook_messages(None) == []


async def test_fetch_teams_messages(pipe, monkeypatch):
    with patch('core.token_storage.token_storage') as ts:
        ts.get_token.return_value = {'access_token': 'tok'}
        chat_msg = {'id': 'cm1', 'createdDateTime': '2026-01-01T10:00:00',
                    'from': {'user': {'displayName': 'Alice', 'email': 'a@b.c'}},
                    'body': {'content': 'hello', 'contentType': 'html'},
                    'attachments': [{'contentType':
                                     'application/vnd.microsoft.card.adaptive',
                                     'content': {'x': 1}}]}
        chan_msg = {'id': 'tm1', 'createdDateTime': '2026-01-01T11:00:00',
                    'from': {'user': {'displayName': 'Bob', 'email': 'b@c.d'}},
                    'body': {'content': 'chan', 'contentType': 'text'}}
        responses = [
            _resp(200, {'value': [{'id': 'ch1', 'chatType': 'group', 'topic': 'T'}]}),
            _resp(200, {'value': [chat_msg]}),
            _resp(403),  # joinedTeams denied
        ]
        _httpx_install(monkeypatch, responses)
        msgs = await pipe._fetch_teams_messages(datetime(2026, 1, 1))
        assert len(msgs) == 1 and msgs[0]['id'] == 'cm1'
        assert msgs[0]['metadata']['adaptive_card'] == {'x': 1}


async def test_fetch_teams_rate_limit_and_errors(pipe, monkeypatch):
    with patch('core.token_storage.token_storage') as ts:
        ts.get_token.return_value = {'access_token': 'tok'}
        chat_msg = {'id': 'cm1',
                    'createdDateTime': '2026-01-01T10:00:00',
                    'body': {'content': 'x'}}
        chan_msg = {'id': 'tm1', 'createdDateTime': '2026-01-01T11:00:00',
                    'body': {'content': 'y'}}
        responses = [
            _resp(200, {'value': [{'id': 'ch1'}, {'id': 'ch2'}]}),
            _resp(429, headers={'Retry-After': '0'}),  # chat1 rate limited
            _resp(200, {'value': [chat_msg]}),          # chat2 ok
            _resp(200, {'value': [{'id': 'T1', 'displayName': 'Team'}]}),
            _resp(200, {'value': [{'id': 'C1', 'displayName': 'General'}]}),
            _resp(200, {'value': [chan_msg]}),
        ]
        _httpx_install(monkeypatch, responses)
        with patch.object(pipe_mod.asyncio, 'sleep', new=AsyncMock()):
            msgs = await pipe._fetch_teams_messages(None)
        assert [m['id'] for m in msgs] == ['cm1', 'tm1']

        # chats endpoint failure -> no chat messages
        _httpx_install(monkeypatch, [_resp(500)])
        assert await pipe._fetch_teams_messages(None) == []

        # outer exception branch
        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError('x'))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(pipe_mod.httpx, 'AsyncClient',
                            MagicMock(return_value=cm))
        assert await pipe._fetch_teams_messages(None) == []


# ============================================================================
# Source connectors — email (IMAP) / gmail / outlook
# ============================================================================

async def test_fetch_email_no_env(pipe, monkeypatch):
    for var in ('IMAP_SERVER', 'IMAP_USER', 'IMAP_PASSWORD'):
        monkeypatch.delenv(var, raising=False)
    assert await pipe._fetch_email_messages(None) == []


async def test_fetch_email_via_executor(pipe, monkeypatch):
    monkeypatch.setenv('IMAP_SERVER', 'imap.x')
    monkeypatch.setenv('IMAP_USER', 'u')
    monkeypatch.setenv('IMAP_PASSWORD', 'p')
    monkeypatch.setattr(pipe, '_fetch_imap_messages',
                        MagicMock(return_value=[{'id': 'e1'}]))
    assert await pipe._fetch_email_messages(None) == [{'id': 'e1'}]


def _build_email_bytes():
    msg = MIMEText('body text here')
    msg['Subject'] = 'Test Subject'
    msg['From'] = 'a@b.c'
    msg['To'] = 'd@e.f'
    msg['Date'] = 'Mon, 01 Jan 2026 10:00:00 +0000'
    msg['Message-ID'] = '<1>'
    return msg.as_bytes()


def test_fetch_imap_messages(pipe, monkeypatch):
    mail = MagicMock()
    mail.search.return_value = ('OK', [b'1 2'])
    mail.fetch.return_value = ('OK', [(b'1', _build_email_bytes())])
    monkeypatch.setattr('imaplib.IMAP4_SSL', MagicMock(return_value=mail))
    msgs = pipe._fetch_imap_messages('srv', 'u', 'p', None)
    assert len(msgs) == 2 and msgs[0]['app_type'] == 'email'
    mail.close.assert_called()
    mail.logout.assert_called()

    # login failure -> []
    mail.login.side_effect = RuntimeError('x')
    assert pipe._fetch_imap_messages('srv', 'u', 'p', None) == []


def test_fetch_imap_search_not_ok(pipe, monkeypatch):
    mail = MagicMock()
    mail.search.return_value = ('NO', [b''])
    monkeypatch.setattr('imaplib.IMAP4_SSL', MagicMock(return_value=mail))
    assert pipe._fetch_imap_messages('srv', 'u', 'p', None) == []


async def test_fetch_gmail_messages(pipe, monkeypatch):
    with patch('integrations.gmail_service.GmailService') as GS:
        inst = GS.return_value
        inst.service = None
        inst._authenticate.side_effect = RuntimeError('x')
        assert await pipe._fetch_gmail_messages(None) == []

        inst._authenticate.side_effect = None
        assert await pipe._fetch_gmail_messages(None) == []

        inst.service = MagicMock()
        inst.get_messages = MagicMock(return_value=[
            {'id': 'g1', 'timestamp': '2026-01-01T10:00:00',
             'sender': 'Alice <a@b.c>', 'recipient': 'x@y.z, z@w.v',
             'subject': 's', 'body': 'b', 'threadId': 't',
             'labelIds': ['IMPORTANT'], 'attachments': [
                 {'id': 'a1', 'filename': 'f', 'size': 1,
                  'contentType': 'text/plain'}]},
            {'id': 'g2', 'timestamp': '1700000000', 'sender': 'plain@b.c',
             'body': 'b2'},
            {'id': 'g3', 'timestamp': object()},  # normalization error skipped
        ])
        msgs = await pipe._fetch_gmail_messages(datetime(2026, 1, 1))
        assert len(msgs) == 2
        assert msgs[0]['sender_email'] == 'a@b.c'
        assert msgs[0]['priority'] == 'high'
        assert msgs[1]['sender'] == 'plain'
        assert msgs[1]['sender_email'] == 'plain@b.c'
        inst.get_messages.assert_called_once()

        inst.get_messages.side_effect = RuntimeError('x')
        assert await pipe._fetch_gmail_messages(None) == []


async def test_fetch_outlook_messages(pipe, monkeypatch):
    with patch('core.token_storage.token_storage') as ts:
        ts.get_token.return_value = {'access_token': 'tok'}
        msg = {'id': 'o1', 'receivedDateTime': '2026-01-01T10:00:00',
               'from': {'emailAddress': {'address': 'a@b.c', 'name': 'A'}},
               'toRecipients': [{'emailAddress': {'address': 'x@y.z'}}],
               'subject': 's', 'body': {'content': 'b', 'contentType': 'html'},
               'attachments': [{'id': 'a', 'name': 'n', 'size': 1,
                                'contentType': 'text/plain', 'isInline': True}],
               'conversationId': 'c', 'importance': 'High', 'isRead': True,
               'categories': ['Work']}
        responses = [
            _resp(429, headers={'Retry-After': '0'}),  # rate limited once
            _resp(200, {'value': [msg], '@odata.nextLink': 'http://next'}),
            _resp(200, {'value': []}),  # second page, no next link
        ]
        _httpx_install(monkeypatch, responses)
        with patch.object(pipe_mod.asyncio, 'sleep', new=AsyncMock()):
            msgs = await pipe._fetch_outlook_messages(datetime(2026, 1, 1))
        assert len(msgs) == 1
        assert msgs[0]['priority'] == 'high' and msgs[0]['status'] == 'read'
        assert 'Work' in msgs[0]['tags']

        # non-200 break and per-page exception
        responses2 = [_resp(500)]
        _httpx_install(monkeypatch, responses2)
        assert await pipe._fetch_outlook_messages(None) == []

        client = MagicMock()
        client.get = AsyncMock(side_effect=RuntimeError('x'))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=client)
        cm.__aexit__ = AsyncMock(return_value=False)
        monkeypatch.setattr(pipe_mod.httpx, 'AsyncClient',
                            MagicMock(return_value=cm))
        assert await pipe._fetch_outlook_messages(None) == []


# ============================================================================
# AtomAIIntegration — helpers
# ============================================================================

def _llm(text='ok'):
    llm = MagicMock()
    llm.generate_completion = AsyncMock(return_value={'content': text})
    return llm


def _ai(**kw):
    cfg = {'llm_service': _llm(),
           'atom_memory_service': MagicMock(),
           'atom_search_service': MagicMock(),
           'atom_workflow_service': MagicMock(),
           'atom_ingestion_pipeline': MagicMock()}
    cfg.update(kw)
    ai = AtomAIIntegration(cfg)
    ai.platform_integrations = {'slack': None, 'teams': None,
                                'google_chat': None, 'discord': None}
    return ai


def test_chat_completion_text_paths():
    m = [{'role': 'user', 'content': 'x'}]
    assert _messages_with_system(m, None) is m
    assert _messages_with_system(m, 'sys')[0]['role'] == 'system'

    async def run():
        assert await _chat_completion_text(None, m) == ''
        llm = MagicMock()
        llm.generate_completion = AsyncMock(return_value={'content': 'a'})
        assert await _chat_completion_text(llm, m, 'sys') == 'a'
        llm2 = MagicMock()
        llm2.generate_completion = AsyncMock(return_value={'text': 'b'})
        assert await _chat_completion_text(llm2, m) == 'b'
        llm3 = MagicMock(spec=[])  # no methods
        assert await _chat_completion_text(llm3, m) == ''
        llm4 = MagicMock(spec=['chat_completion'])
        llm4.chat_completion = AsyncMock(return_value='c')
        assert await _chat_completion_text(llm4, m, 'sys') == 'c'
        llm5 = MagicMock(spec=['chat_completion'])
        llm5.chat_completion = AsyncMock(return_value=None)
        assert await _chat_completion_text(llm5, m) == ''
    asyncio.run(run())


def test_ai_platform_detection():
    ai = _ai()
    assert ai._get_platform_from_workspace('slack_T1') == 'slack'
    assert ai._get_platform_from_workspace('teams_T1') == 'teams'
    assert ai._get_platform_from_workspace('google_chat_T1') == 'google_chat'
    assert ai._get_platform_from_workspace('discord_T1') == 'discord'
    assert ai._get_platform_from_workspace('other') == 'unknown'
    assert ai._get_platform_from_channel('slack_C1') == 'slack'
    assert ai._get_platform_from_channel('teams_C1') == 'teams'
    assert ai._get_platform_from_channel('google_chat_C1') == 'google_chat'
    assert ai._get_platform_from_channel('discord_C1') == 'discord'
    assert ai._get_platform_from_channel('C1') == 'unknown'


async def test_ai_init_and_initialize():
    ai = _ai(atom_memory_service=None)
    assert await ai.initialize() is False
    ai = _ai()
    ai._start_ai_integration_workers = AsyncMock()
    assert await ai.initialize() is True
    assert ai.is_initialized and 'intelligent_search' in ai.active_ai_features

    ai2 = _ai()
    ai2._start_ai_integration_workers = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await ai2.initialize() is False


def _ws(member_count=10, channel_count=2):
    return {'id': 'w1', 'name': 'W', 'platform': 'slack', 'type': 'team',
            'status': 'active', 'member_count': member_count,
            'channel_count': channel_count, 'icon_url': '',
            'description': 'd', 'capabilities': {'voice_chat': False},
            'integration_data': {}}


async def test_get_intelligent_workspaces():
    ai = _ai()
    integ = MagicMock()
    integ.get_unified_workspaces = AsyncMock(
        return_value=[_ws(150, 30), _ws(60, 15), _ws()])
    ai.platform_integrations['slack'] = integ
    ws = await ai.get_intelligent_workspaces('u')
    assert len(ws) == 3
    assert ws[0]['ai_insights']['engagement_level'] == 'high'
    assert ws[1]['ai_insights']['engagement_level'] == 'medium'
    assert ws[2]['ai_insights']['engagement_level'] == 'low'

    integ.get_unified_workspaces = AsyncMock(side_effect=RuntimeError('x'))
    assert await ai.get_intelligent_workspaces('u') == []


def _ch(message_count=10, member_count=1):
    return {'id': 'c1', 'name': 'general', 'display_name': 'General',
            'type': 'channel', 'platform': 'slack', 'workspace_id': 'w1',
            'workspace_name': 'W', 'status': 'active',
            'member_count': member_count, 'message_count': message_count,
            'unread_count': 0, 'is_private': False, 'is_text': True,
            'is_voice': False, 'capabilities': {}, 'integration_data': {}}


async def test_get_intelligent_channels():
    ai = _ai()
    integ = MagicMock()
    integ.get_unified_channels = AsyncMock(
        return_value=[_ch(600, 30), _ch(300, 15), _ch()])
    ai.platform_integrations['slack'] = integ
    chans = await ai.get_intelligent_channels('slack_w1')
    assert len(chans) == 3
    assert chans[0]['ai_insights']['engagement_level'] == 'high'
    assert chans[1]['ai_insights']['engagement_level'] == 'medium'
    assert chans[2]['ai_insights']['engagement_level'] == 'low'

    ai.platform_integrations['slack'] = None
    assert await ai.get_intelligent_channels('slack_w1') == []
    ai.platform_integrations['slack'] = MagicMock()
    ai.platform_integrations['slack'].get_unified_channels = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await ai.get_intelligent_channels('slack_w1') == []


def _msg():
    keys = ['id', 'content', 'html_content', 'platform', 'workspace_id',
            'channel_id', 'user_id', 'user_name', 'user_display_name',
            'user_avatar', 'timestamp', 'thread_id', 'reply_to_id',
            'message_type', 'is_edited', 'is_pinned', 'is_bot', 'is_webhook',
            'reactions', 'attachments', 'embeds', 'mentions', 'files',
            'integration_data', 'metadata']
    return {k: None for k in keys} | {
        'id': 'm1', 'content': 'hello world', 'platform': 'slack'}


async def test_get_intelligent_messages():
    ai = _ai()
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': json.dumps(
            {'sentiment': 'positive', 'sentiment_score': 0.9,
             'key_topics': ['x']})})
    integ = MagicMock()
    integ.get_unified_messages = AsyncMock(return_value=[_msg()])
    ai.platform_integrations['slack'] = integ
    msgs = await ai.get_intelligent_messages('w', 'slack_c', options={
        'translation_language': 'fr'})
    assert msgs[0]['ai_analysis']['sentiment'] == 'positive'
    assert msgs[0]['ai_features']['translation_target'] == 'fr'

    ai.platform_integrations['slack'] = None
    assert await ai.get_intelligent_messages('w', 'slack_c') == []
    ai.platform_integrations['slack'] = MagicMock()
    ai.platform_integrations['slack'].get_unified_messages = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await ai.get_intelligent_messages('w', 'slack_c') == []


async def test_intelligent_search_routing():
    ai = _ai()
    ai.search_manager = MagicMock()
    ai.search_manager.search = AsyncMock(return_value=[{'id': 'r'}])
    assert await ai.intelligent_search('q') == [{'id': 'r'}]
    ai.search_manager.search = AsyncMock(side_effect=RuntimeError('x'))
    assert await ai.intelligent_search('q') == []


async def test_send_intelligent_message():
    ai = _ai()
    ai._enhance_content = AsyncMock(return_value='enhanced')
    assert (await ai.send_intelligent_message('w', 'other_c', 'hi')) == {
        'ok': False, 'error': 'Unsupported platform'}
    integ = MagicMock()
    integ.send_unified_message = AsyncMock(
        return_value={'ok': True, 'message_id': 'm'})
    ai.platform_integrations['slack'] = integ
    ai._analyze_message_after_send = AsyncMock()
    res = await ai.send_intelligent_message('slack_w', 'slack_c', 'hi')
    assert res['ok'] is True
    ai._analyze_message_after_send.assert_awaited_once()

    ai._enhance_content = AsyncMock(side_effect=RuntimeError('x'))
    assert (await ai.send_intelligent_message('w', 'c', 'hi'))['ok'] is False


async def test_create_intelligent_workflow():
    ai = _ai()
    ai.workflow_intelligence.enhance_workflow = AsyncMock(
        return_value={'name': 'wf'})
    ai.atom_workflow.create_workflow = AsyncMock(return_value={'ok': True})
    assert (await ai.create_intelligent_workflow({'name': 'wf'}))['ok'] is True

    ai.atom_workflow = None
    assert (await ai.create_intelligent_workflow({}))['error'] == \
        'Workflow service not available'

    ai.workflow_intelligence.enhance_workflow = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await ai.create_intelligent_workflow({}))['ok'] is False


async def test_get_intelligent_analytics():
    ai = _ai()
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"insight": 1}'})
    res = await ai.get_intelligent_analytics('metric', '7d')
    assert res == {'insight': 1}
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'plain'})
    assert (await ai.get_intelligent_analytics('m', 'r')) == {
        'analysis': 'plain'}
    ai.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await ai.get_intelligent_analytics('m', 'r'))['ok'] is False


async def test_conversation_wrappers():
    ai = _ai()
    ai.conversation_manager.start_conversation = AsyncMock(return_value='cid')
    assert await ai.start_ai_conversation('u', 'slack') == 'cid'
    ai.conversation_manager.start_conversation = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await ai.start_ai_conversation('u', 'slack') == ''

    ai.conversation_manager.continue_conversation = AsyncMock(
        return_value={'ok': True})
    assert (await ai.continue_ai_conversation('cid', 'm', 'u'))['ok'] is True
    ai.conversation_manager.continue_conversation = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await ai.continue_ai_conversation('cid', 'm', 'u'))['ok'] is False

    ai.conversation_manager.process_command = AsyncMock(
        return_value={'ok': True})
    assert (await ai.process_natural_language_command('c', 'u'))['ok'] is True
    ai.conversation_manager.process_command = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await ai.process_natural_language_command('c', 'u'))['ok'] is False


async def test_message_ai_analysis_paths():
    ai = _ai()
    ai.llm_service.generate_completion = AsyncMock(return_value={'content': json.dumps(
        {'sentiment': 'negative', 'sentiment_score': -0.5, 'key_topics': ['t']})})
    res = await ai._get_message_ai_analysis({'content': 'msg'})
    assert res['sentiment'] == 'negative'
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'not json'})
    res = await ai._get_message_ai_analysis({'content': 'msg'})
    assert res['confidence'] == 0.5
    ai.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    res = await ai._get_message_ai_analysis({'content': 'msg'})
    assert res['confidence'] == 0.0


async def test_enhance_content():
    ai = _ai()
    assert await ai._enhance_content('keep', {'enhance_content': False}) == 'keep'
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'enhanced'})
    assert await ai._enhance_content('c', {}) == 'enhanced'
    ai.llm_service.generate_completion = AsyncMock(
        return_value={'content': ''})
    assert await ai._enhance_content('c', {}) == 'c'
    ai.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await ai._enhance_content('c', {}) == 'c'


async def test_analyze_message_after_send():
    ai = _ai()
    ai.atom_memory = None
    await ai._analyze_message_after_send({}, {'analyze_after_send': False})
    ai.atom_memory = MagicMock()
    ai.atom_memory.store = AsyncMock()
    await ai._analyze_message_after_send({'message_id': 'm'}, {})
    ai.atom_memory.store.assert_awaited_once()
    ai.atom_memory.store = AsyncMock(side_effect=RuntimeError('x'))
    await ai._analyze_message_after_send({}, {})


# ============================================================================
# AIConversationManager / IntelligentSearchManager / Workflow / CrossPlatform
# ============================================================================

async def test_conversation_manager():
    cm = AIConversationManager(_llm())
    cid = await cm.start_conversation('u1', 'slack', workspace_id='w')
    assert cid.startswith('ai_conv_u1_slack_w')
    assert (await cm.continue_conversation('missing', 'm', 'u')) == {
        'ok': False, 'error': 'Conversation not found'}
    cm.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'answer'})
    res = await cm.continue_conversation(cid, 'hello', 'u1')
    assert res['ok'] is True and res['response'] == 'answer'
    cm.llm_service.generate_completion = AsyncMock(return_value={'content': ''})
    res = await cm.continue_conversation(cid, 'again', 'u1')
    assert res['ok'] is False

    cm2 = AIConversationManager(_llm())
    cm2.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await cm2.continue_conversation('x', 'm', 'u'))['ok'] is False
    assert (await cm2.process_command('cmd', 'u'))['ok'] is False

    cm3 = AIConversationManager(_llm())
    cm3.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"action": "send"}'})
    assert (await cm3.process_command('cmd', 'u')) == {'action': 'send'}
    cm3.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'raw text'})
    assert (await cm3.process_command('cmd', 'u')) == {
        'ok': True, 'response': 'raw text'}


async def test_search_manager():
    sm = IntelligentSearchManager(_llm(), MagicMock())
    await sm.initialize()
    assert sm.search_index['documents'] == []
    sm.atom_search.unified_search = AsyncMock(return_value=[])
    assert await sm.search('q') == []
    sm.atom_search.unified_search = AsyncMock(return_value=[{'id': 1}])
    sm.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"ranked_results": [{"id": 2}]}'})
    assert await sm.search('q') == [{'id': 2}]
    sm.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'garbage'})
    assert await sm.search('q') == [{'id': 1}]
    sm.atom_search.unified_search = AsyncMock(side_effect=RuntimeError('x'))
    assert await sm.search('q') == []
    # no llm method at all
    sm2 = IntelligentSearchManager(MagicMock(spec=[]), MagicMock())
    sm2.atom_search.unified_search = AsyncMock(return_value=[{'id': 1}])
    assert await sm2.search('q') == [{'id': 1}]


async def test_update_search_index():
    sm = IntelligentSearchManager(_llm(), MagicMock(), atom_ingestion=MagicMock())
    sm._get_recent_communications = AsyncMock(return_value=[])
    await sm.update_search_index()
    sm._index_communication = AsyncMock()
    sm._get_recent_communications = AsyncMock(return_value=[{'id': 'c'}])
    await sm.update_search_index()
    sm._index_communication.assert_awaited_once()
    sm._get_recent_communications = AsyncMock(side_effect=RuntimeError('x'))
    await sm.update_search_index()  # error branch


async def test_index_communication():
    sm = IntelligentSearchManager(_llm(), MagicMock())
    await sm._index_communication({'id': 'x', 'body': 'short'})
    with patch('core.embedding_service.EmbeddingService') as ES, \
            patch('core.lancedb_handler.get_lancedb_handler') as gh:
        ES.return_value.generate_embedding = AsyncMock(return_value=[0.1])
        gh.return_value.upsert = AsyncMock()
        await sm._index_communication(
            {'id': 'c1', 'subject': 's', 'body': 'b' * 20, 'sender': 'x',
             'timestamp': '2026', 'platform': 'slack'})
        gh.return_value.upsert.assert_awaited_once()
        ES.return_value.generate_embedding.side_effect = RuntimeError('x')
        await sm._index_communication(
            {'id': 'c2', 'body': 'b' * 20})


async def test_workflow_intelligence():
    wi = WorkflowIntelligenceManager(_llm(), MagicMock())
    await wi.initialize()
    assert 'approval_patterns' in wi.workflow_patterns
    wi.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"suggestions": ["x"]}'})
    wf = await wi.enhance_workflow({'name': 'wf'})
    assert wf['ai_enhancements'] == {'suggestions': ['x']}
    wi.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'text'})
    wf = await wi.enhance_workflow({'name': 'wf'})
    assert wf['ai_enhancements'] == {'suggestions': 'text'}
    wi.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await wi.enhance_workflow({'name': 'wf'}))['name'] == 'wf'

    wi._get_all_workflows = AsyncMock(return_value=[{'id': 'w1'}])
    wi.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"op": 1}'})
    wi._apply_optimizations = AsyncMock()
    await wi.optimize_workflows()
    wi._apply_optimizations.assert_awaited_once()
    wi.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'not json'})
    await wi.optimize_workflows()
    wi._get_all_workflows = AsyncMock(side_effect=None)
    wi.atom_workflow = None
    await wi.optimize_workflows()
    await wi.setup_workflow_automation()
    await wi.start_monitoring()


async def test_cross_platform_ai():
    cp = CrossPlatformAIManager(_llm(), {'slack': MagicMock()})
    await cp.initialize()
    assert 'slack' in cp.cross_platform_insights['platforms']
    cp.llm_service.generate_completion = AsyncMock(
        return_value={'content': '{"insight": 1}'})
    await cp.synchronize_ai_insights()
    assert cp.cross_platform_insights == {'insight': 1}
    cp.llm_service.generate_completion = AsyncMock(
        return_value={'content': 'text'})
    await cp.synchronize_ai_insights()
    assert cp.cross_platform_insights == {'analysis': 'text'}
    cp.llm_service.generate_completion = AsyncMock(
        side_effect=RuntimeError('x'))
    await cp.synchronize_ai_insights()
    insights = await cp._get_platform_insights('slack', MagicMock())
    assert insights['platform'] == 'slack'
    data = await cp._get_platform_data('slack')
    assert data['connected'] is False


async def test_ai_background_workers():
    ai = _ai()
    ai.search_manager = MagicMock()
    ai.search_manager.update_search_index = AsyncMock()
    ai.workflow_intelligence = MagicMock()
    ai.workflow_intelligence.optimize_workflows = AsyncMock()
    ai.cross_platform_ai = MagicMock()
    ai.cross_platform_ai.synchronize_ai_insights = AsyncMock()

    async def cancel_sleep(secs):
        raise asyncio.CancelledError()

    with patch.object(ai_mod.asyncio, 'sleep', side_effect=cancel_sleep):
        for worker in (ai._ai_message_analysis_worker,
                       ai._intelligent_search_indexing_worker,
                       ai._ai_workflow_optimization_worker,
                       ai._cross_platform_ai_worker):
            with pytest.raises(asyncio.CancelledError):
                await worker()

    async def err_sleep(secs):
        raise RuntimeError('worker boom')

    with patch.object(ai_mod.asyncio, 'sleep', side_effect=err_sleep):
        for worker in (ai._ai_message_analysis_worker,
                       ai._intelligent_search_indexing_worker,
                       ai._ai_workflow_optimization_worker,
                       ai._cross_platform_ai_worker):
            # error branch sleeps again -> RuntimeError again -> escapes
            with pytest.raises(RuntimeError):
                await worker()


def test_global_instance_exists():
    assert ai_mod.atom_ai_integration is not None
