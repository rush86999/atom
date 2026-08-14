# -*- coding: utf-8 -*-
"""Coverage wave 86 — integrations.atom_telegram_integration,
integrations.atom_google_chat_integration.

No network, no LLM: all HTTP is mocked (httpx.AsyncClient), all service
boundaries (enterprise security/automation, AI, memory/search/workflow,
google chat enhanced service) are AsyncMock/MagicMock objects.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_google_chat_integration as gc_mod
import integrations.atom_telegram_integration as tg_mod
from integrations.atom_telegram_integration import (
    AtomTelegramIntegration,
    TelegramChat,
    TelegramChatType,
    TelegramMessage,
    TelegramMessageType,
)
from integrations.atom_google_chat_integration import AtomGoogleChatIntegration


# ============================================================================
# Helpers
# ============================================================================

def _httpx_payload(monkeypatch, payload=None, post_exc=None):
    """Patch httpx.AsyncClient so every POST returns `payload` (or raises)."""
    resp = MagicMock()
    resp.json.return_value = payload if payload is not None else {}
    client_cls = MagicMock()
    client = client_cls.return_value.__aenter__.return_value
    if post_exc is not None:
        client.post = AsyncMock(side_effect=post_exc)
    else:
        client.post = AsyncMock(return_value=resp)
    monkeypatch.setattr('httpx.AsyncClient', client_cls)
    return client


DT = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture()
def tg():
    integ = AtomTelegramIntegration({'bot_token': 'tok123'})
    integ.lancedb_handler = None
    return integ


def mk_chat(chat_id=1, active=True, title='Team Chat'):
    return TelegramChat(
        chat_id=chat_id, chat_type=TelegramChatType.GROUP, title=title,
        username='teamchat', first_name=None, last_name=None,
        description='a chat', permissions={'send': True},
        security_level='standard', is_active=active, member_count=3,
        created_at=DT, last_message=DT, metadata={})


def mk_msg(message_id=1, chat_id=1, user_id=10, content='hello world'):
    return TelegramMessage(
        message_id=message_id, chat_id=chat_id, user_id=user_id,
        message_type=TelegramMessageType.TEXT, content=content,
        media_path=None, reply_to_message_id=None, forward_from=None,
        forward_from_chat=None, edit_date=None, timestamp=DT, views=0,
        reactions=[], security_flags={}, metadata={})


@pytest.fixture()
def gchat():
    integ = AtomGoogleChatIntegration({})
    integ.google_chat_service = MagicMock()
    return integ


def gc_space(space_id='S1', active=True, space_type='ROOM'):
    return SimpleNamespace(
        space_id=space_id, display_name='Space One', is_active=active,
        member_count=4, type=space_type, space_threading_state='THREADED',
        space_uri='https://chat.google.com/room/S1',
        space_permission_level='SPACE_MEMBER', threaded=True,
        created_at=DT, description='desc', is_archived=False,
        message_count=7, last_modified_at='2026-08-10T00:00:00Z',
        single_user_bot_dm=False, external_user_permission=None)


def gc_message(message_id='M1', with_integration_data=False):
    msg = SimpleNamespace(
        message_id=message_id, text='deploy the service now',
        formatted_text='<b>deploy</b>', user_id='U1', user_name='Alice',
        user_email='a@x.com', user_avatar='av', timestamp='2026-08-10T00:00:00Z',
        thread_id='T1', reply_to_id=None, message_type='TEXT', is_edited=True,
        edit_timestamp='2026-08-10T01:00:00Z',
        reactions=[{'emoji': '👍', 'count': 2, 'user_ids': ['U1', 'U2']}],
        attachment=[{'name': 'f1', 'title': 'file.pdf',
                     'contentType': 'application/pdf',
                     'downloadUri': 'd', 'thumbnailUri': 't', 'size': 10}],
        annotations=[{'type': 'user_mention',
                      'userMention': {'name': 'users/U1', 'displayName': 'Alice'}}],
        gu_id='gu', sender_type='HUMAN', space_threading_state='THREADED',
        thread_name='threads/T1', thread_id_created_by='U1',
        quoted_message_id=None, card_v2=[{'cardId': 'c'}],
        slash_command=None, action_response=None, arguments=[],
        space_id='S1')
    if with_integration_data:
        msg.integration_data = {'search_score': 0.9}
    return msg


# ============================================================================
# Telegram — initialization & lifecycle
# ============================================================================

async def test_tg_initialize_no_token():
    integ = AtomTelegramIntegration({'bot_token': None})
    assert await integ.initialize() is False


async def test_tg_initialize_success(tg, monkeypatch):
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN', raising=False)
    tg.enterprise_security = MagicMock()
    tg.enterprise_security.audit_event = AsyncMock()
    tg.enterprise_automation = MagicMock()
    tg.enterprise_automation.create_integration_automation = AsyncMock(
        return_value={'ok': True})
    assert await tg.initialize() is True
    assert tg.is_initialized is True
    assert tg.security_policies and tg.compliance_rules
    assert tg.automation_triggers and tg.security_monitoring
    assert tg.compliance_monitoring


async def test_tg_initialize_automation_fail(tg):
    tg.enterprise_security = None
    tg.enterprise_automation = None
    tg.telegram_config['enable_enterprise_features'] = False
    assert await tg.initialize() is True  # automation skipped via warning
    # automation exists and returns not-ok
    tg2 = AtomTelegramIntegration({'bot_token': 't'})
    tg2.enterprise_automation = MagicMock()
    tg2.enterprise_automation.create_integration_automation = AsyncMock(
        return_value={'ok': False, 'error': 'bad'})
    await tg2._setup_automation()
    # automation raises
    tg2.enterprise_automation.create_integration_automation = AsyncMock(
        side_effect=RuntimeError('boom'))
    await tg2._setup_automation()


async def test_tg_initialize_exception(tg, monkeypatch):
    monkeypatch.setattr(tg, '_load_existing_data',
                        AsyncMock(side_effect=RuntimeError('db')))
    assert await tg.initialize() is False


async def test_tg_setup_enterprise_missing_services(tg):
    tg.enterprise_security = None
    tg.enterprise_automation = None
    await tg._setup_enterprise_features()  # warning path


async def test_tg_close_and_start_bot(tg):
    await tg._start_bot()
    assert tg._start_time > 0
    await tg.close()


# ============================================================================
# Telegram — workspaces / search / history / status
# ============================================================================

async def test_tg_intelligent_workspaces_and_channels(tg):
    tg.active_chats = {1: mk_chat(1, title='Zed'), 2: mk_chat(2, title='Aaa'),
                       3: mk_chat(3, active=False)}
    ws = await tg.get_intelligent_workspaces(user_id=10)
    assert len(ws) == 2 and ws[0]['name'] == 'Zed'  # inactive chat excluded
    chans = await tg.get_intelligent_channels(1, user_id=10)
    assert chans[0]['id'] == 1 and chans[0]['platform'] == 'telegram'
    assert await tg.get_intelligent_channels(99, 10) == []


async def test_tg_intelligent_search(tg):
    tg.message_history = {
        1: [mk_msg(1, content='deploy now'), mk_msg(2, content='hello there')],
    }
    res = await tg.perform_intelligent_search('deploy now', 10)
    assert res and res[0]['type'] == 'telegram_message'
    res2 = await tg.perform_intelligent_search('deploy', 10, workspace_id=1)
    assert len(res2) == 1
    assert tg._calculate_relevance_score('a b', 'a c') == 0.5
    assert tg._calculate_relevance_score('', 'x') == 0.0
    # exception branch: non-string content
    tg.message_history = {1: [mk_msg(content=123)]}
    assert await tg.perform_intelligent_search('x', 10) == []


async def test_tg_ai_search_branches(tg, monkeypatch):
    assert await tg._perform_ai_search('q') == []  # ai_service None
    tg.ai_service = MagicMock()
    monkeypatch.setattr(tg_mod, 'AIRequest', None)
    assert await tg._perform_ai_search('q') == []  # AIRequest unavailable
    monkeypatch.setattr(tg_mod, 'AIRequest', MagicMock())
    monkeypatch.setattr(tg_mod, 'AITaskType', MagicMock(SEARCH_QUERY='sq'))
    monkeypatch.setattr(tg_mod, 'AIModelType', MagicMock(GPT_4='g4'))
    monkeypatch.setattr(tg_mod, 'AIServiceType', MagicMock(OPENAI='oa'))
    resp = MagicMock(ok=True, output_data={'results': [{'id': 'r1'}]})
    tg.ai_service.process_ai_request = AsyncMock(return_value=resp)
    assert await tg._perform_ai_search('q') == [{'id': 'r1'}]
    resp2 = MagicMock(ok=False, output_data=None)
    tg.ai_service.process_ai_request = AsyncMock(return_value=resp2)
    assert await tg._perform_ai_search('q') == []
    tg.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await tg._perform_ai_search('q') == []


async def test_tg_conversation_history(tg):
    tg.message_history = {1: [mk_msg(1, user_id=10), mk_msg(2, user_id=20),
                              mk_msg(3, user_id=10)]}
    hist = await tg.get_user_conversation_history(10, 1)
    assert len(hist) == 2 and hist[0]['platform'] == 'telegram'
    # exception branch
    bad = MagicMock()
    bad.get.side_effect = RuntimeError('x')
    tg.message_history = bad
    assert await tg.get_user_conversation_history(10, 1) == []


async def test_tg_service_status(tg):
    status = await tg.get_service_status()
    assert status['platform'] == 'telegram'
    assert 'total_messages' in status and 'uptime' in status


async def test_tg_log_message_event(tg):
    tg.enterprise_security = MagicMock()
    tg.enterprise_security.audit_event = AsyncMock()
    await tg._log_message_event('message_received', 1, {'user_id': 10})
    tg.enterprise_security.audit_event.assert_awaited_once()
    tg.enterprise_security.audit_event = AsyncMock(side_effect=RuntimeError('x'))
    await tg._log_message_event('x', 1, {})  # swallowed


# ============================================================================
# Telegram — HTTP API methods
# ============================================================================

async def test_tg_send_message_with_keyboard(tg, monkeypatch):
    client = _httpx_payload(monkeypatch, {'ok': True, 'result': {'message_id': 42}})
    res = await tg.send_message_with_keyboard(
        1, 'hi', [[{'text': 'b'}]], parse_mode='Markdown',
        disable_web_page_preview=True, disable_notification=True,
        reply_to_message_id=5)
    assert res['success'] is True and res['message_id'] == 42
    payload = client.post.call_args.kwargs['json']
    assert payload['reply_markup']['inline_keyboard'] == [[{'text': 'b'}]]

    _httpx_payload(monkeypatch, {'ok': False, 'description': 'nope'})
    assert (await tg.send_message_with_keyboard(1, 'hi', []))['error'] == 'nope'

    _httpx_payload(monkeypatch, post_exc=RuntimeError('net'))
    assert (await tg.send_message_with_keyboard(1, 'hi', []))['success'] is False

    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.send_message_with_keyboard(1, 'x', []))['success'] is False


async def test_tg_edit_message_keyboard(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True})
    res = await tg.edit_message_keyboard(1, 5, [[{'text': 'b'}]])
    assert res['success'] is True and res['message_id'] == 5
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'bad'})
    assert (await tg.edit_message_keyboard(1, 5, []))['success'] is False
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.edit_message_keyboard(1, 5, []))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.edit_message_keyboard(1, 5, []))['success'] is False


async def test_tg_answer_callback_query(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True})
    res = await tg.answer_callback_query(
        'cb1', text='hi', show_alert=True, url='https://x', cache_time=5)
    assert res['success'] is True
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'err'})
    assert (await tg.answer_callback_query('cb1'))['error'] == 'err'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.answer_callback_query('cb1'))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.answer_callback_query('cb1'))['success'] is False


async def test_tg_answer_inline_query(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True})
    res = await tg.answer_inline_query(
        'iq1', [{'id': 'a', 'title': 't', 'description': 'd', 'message': 'm'}],
        personal=True, next_offset='2')
    assert res['success'] is True
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.answer_inline_query('iq1', []))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.answer_inline_query('iq1', []))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.answer_inline_query('iq1', []))['success'] is False


async def test_tg_send_chat_action(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True})
    res = await tg.send_chat_action(1, 'typing', progress=50)
    assert res['success'] is True and res['action'] == 'typing'
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.send_chat_action(1, 'typing'))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.send_chat_action(1, 'typing'))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.send_chat_action(1, 'typing'))['success'] is False


async def test_tg_send_intelligent_message(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True, 'result': {'message_id': 9}})
    res = await tg.send_intelligent_message(
        1, 'msg', metadata={'a': 1}, parse_mode='HTML',
        disable_web_page_preview=False, disable_notification=True,
        reply_to_message_id=3)
    assert res['success'] is True
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.send_intelligent_message(1, 'm'))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.send_intelligent_message(1, 'm'))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.send_intelligent_message(1, 'm'))['success'] is False


async def test_tg_send_photo(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True, 'result': {'message_id': 7}})
    res = await tg.send_photo(1, 'http://img', caption='cap', parse_mode='HTML')
    assert res['success'] is True and res['message_id'] == 7
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.send_photo(1, 'p'))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.send_photo(1, 'p'))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.send_photo(1, 'p'))['success'] is False


async def test_tg_send_poll(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True, 'result': {'message_id': 3,
                                                        'poll_id': 'p1'}})
    res = await tg.send_poll(1, 'Q?', ['a', 'b'], is_anonymous=True,
                             allows_multiple_answers=True, explanation='why')
    assert res['success'] is True and res['poll_id'] == 'p1'
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.send_poll(1, 'Q', ['a']))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.send_poll(1, 'Q', ['a']))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.send_poll(1, 'Q', ['a']))['success'] is False


async def test_tg_get_chat_info(tg, monkeypatch):
    _httpx_payload(monkeypatch, {'ok': True, 'result': {'id': 1, 'title': 'T'}})
    res = await tg.get_chat_info(1)
    assert res['success'] is True and res['chat_info']['title'] == 'T'
    _httpx_payload(monkeypatch, {'ok': False, 'description': 'e'})
    assert (await tg.get_chat_info(1))['error'] == 'e'
    _httpx_payload(monkeypatch, post_exc=RuntimeError('x'))
    assert (await tg.get_chat_info(1))['success'] is False
    no_tok = AtomTelegramIntegration({})
    assert (await no_tok.get_chat_info(1))['success'] is False


# ============================================================================
# Telegram — callback query routing
# ============================================================================

@pytest.fixture()
def tg_cb(tg):
    tg.answer_callback_query = AsyncMock(return_value={'success': True})
    return tg


async def test_tg_handle_callback_query_routing(tg_cb):
    await tg_cb.handle_callback_query({'id': '1', 'data': 'action_approve_9',
                                       'message': {}, 'from': {'id': 5}})
    assert tg_cb.answer_callback_query.await_count == 2  # ack + result
    await tg_cb.handle_callback_query({'id': '1', 'data': 'zzz_unknown',
                                       'from': {}})
    assert tg_cb.answer_callback_query.await_args.kwargs.get('show_alert') is True
    await tg_cb.handle_callback_query({'id': '1', 'data': '', 'from': {}})
    # exception swallowed
    tg_cb.answer_callback_query = AsyncMock(side_effect=RuntimeError('x'))
    await tg_cb.handle_callback_query({'id': '1', 'data': 'action_x', 'from': {}})


async def test_tg_action_callback_branches(tg_cb):
    await tg_cb._handle_action_callback('cb', 'action', 1)  # invalid format
    await tg_cb._handle_action_callback('cb', 'action_approve_request', 1)
    await tg_cb._handle_action_callback('cb', 'action_approve_request_5', 1)
    await tg_cb._handle_action_callback('cb', 'action_deny_request', 1)
    await tg_cb._handle_action_callback('cb', 'action_deny_request_5', 1)
    await tg_cb._handle_action_callback('cb', 'action_execute_workflow', 1)
    await tg_cb._handle_action_callback('cb', 'action_execute_workflow_7', 1)
    await tg_cb._handle_action_callback('cb', 'action_bogus_thing', 1)
    # routing exception -> error alert
    tg_cb._handle_approve_request = AsyncMock(side_effect=RuntimeError('x'))
    await tg_cb._handle_action_callback('cb', 'action_approve_request_1', 1)


async def test_tg_search_callback_branches(tg_cb):
    await tg_cb._handle_search_callback('cb', 'search', 1)  # invalid
    await tg_cb._handle_search_callback('cb', 'search_recent', 1)
    await tg_cb._handle_search_callback('cb', 'search_communications_query', 1)
    await tg_cb._handle_search_callback('cb', 'search_workflows_query', 1)
    await tg_cb._handle_search_callback('cb', 'search_bogus_x', 1)
    tg_cb._handle_search_recent_messages = AsyncMock(side_effect=RuntimeError('x'))
    await tg_cb._handle_search_callback('cb', 'search_recent', 1)


async def test_tg_workflow_callback_branches(tg_cb):
    await tg_cb._handle_workflow_callback('cb', 'workflow_1', 1)  # invalid
    await tg_cb._handle_workflow_callback('cb', 'workflow_1_start', 1)
    await tg_cb._handle_workflow_callback('cb', 'workflow_1_stop', 1)
    await tg_cb._handle_workflow_callback('cb', 'workflow_1_status', 1)
    await tg_cb._handle_workflow_callback('cb', 'workflow_1_bogus', 1)
    tg_cb._handle_start_workflow = AsyncMock(side_effect=RuntimeError('x'))
    await tg_cb._handle_workflow_callback('cb', 'workflow_1_start', 1)


async def test_tg_settings_callback_branches(tg_cb):
    await tg_cb._handle_settings_callback('cb', 'settings_x', 1)  # invalid
    await tg_cb._handle_settings_callback('cb', 'settings_notifications_on', 1)
    await tg_cb._handle_settings_callback('cb', 'settings_language_fr', 1)
    await tg_cb._handle_settings_callback('cb', 'settings_theme_dark', 1)
    await tg_cb._handle_settings_callback('cb', 'settings_bogus_x', 1)
    tg_cb._handle_theme_setting = AsyncMock(side_effect=RuntimeError('x'))
    await tg_cb._handle_settings_callback('cb', 'settings_theme_dark', 1)


async def test_tg_sub_handlers(tg_cb):
    await tg_cb._handle_approve_request('cb', ['r1'], 1)
    await tg_cb._handle_deny_request('cb', ['r1'], 1)
    await tg_cb._handle_execute_workflow('cb', ['w1'], 1)
    await tg_cb._handle_search_recent_messages('cb', 1)
    await tg_cb._handle_search_communications('cb', 'q', 1)
    await tg_cb._handle_search_workflows('cb', 'q', 1)
    await tg_cb._handle_start_workflow('cb', 'w', 1)
    await tg_cb._handle_stop_workflow('cb', 'w', 1)
    await tg_cb._handle_workflow_status('cb', 'w', 1)
    await tg_cb._handle_notifications_setting('cb', 'on', 1)
    await tg_cb._handle_language_setting('cb', 'fr', 1)
    await tg_cb._handle_theme_setting('cb', 'dark', 1)
    assert tg_cb.answer_callback_query.await_count == 12


# ============================================================================
# Telegram — inline query handling
# ============================================================================

async def test_tg_handle_inline_query_simple(tg):
    tg.answer_inline_query = AsyncMock(return_value={'success': True})
    await tg.handle_inline_query({'id': 'q1', 'query': 'deploy',
                                  'from': {'id': 5}})
    tg.answer_inline_query.assert_awaited_once()
    args = tg.answer_inline_query.await_args.kwargs
    assert args['results'][0]['id'] == 'help_1'
    # short query -> empty results
    await tg.handle_inline_query({'id': 'q2', 'query': 'd', 'from': {}})
    assert tg.answer_inline_query.await_args.kwargs['results'] == []


async def test_tg_handle_inline_query_lancedb(tg):
    tg.answer_inline_query = AsyncMock()
    tg.lancedb_handler = MagicMock()
    tg.lancedb_handler.search.return_value = [
        {'id': 'c1', 'subject': 'Subj', 'body': 'body text', 'sender': 's',
         'platform': 'slack', 'timestamp': 't'}]
    await tg.handle_inline_query({'id': 'q', 'query': 'body', 'from': {}})
    results = tg.answer_inline_query.await_args.kwargs['results']
    assert results[0]['id'] == 'c1' and results[0]['title'] == 'Subj'
    # lancedb failure falls back to simple search
    tg.lancedb_handler.search.side_effect = RuntimeError('db')
    await tg.handle_inline_query({'id': 'q', 'query': 'body', 'from': {}})
    assert tg.answer_inline_query.await_args.kwargs['results'][0]['id'] == 'help_1'
    # handler-level exception swallowed
    tg.answer_inline_query = AsyncMock(side_effect=RuntimeError('x'))
    await tg.handle_inline_query({'id': 'q', 'query': 'body', 'from': {}})


def test_tg_format_lancedb_result(tg):
    long_body = 'x' * 300
    out = tg._format_lancedb_result_for_inline(
        {'id': 'i1', 'subject': 's', 'body': long_body, 'sender': 'a',
         'platform': 'p', 'timestamp': 't'})
    assert out['id'] == 'i1' and '...' in out['input_message_content']['message_text']
    no_id = tg._format_lancedb_result_for_inline(
        {'subject': 's', 'body': 'b', 'sender': 'a', 'platform': 'p'})
    assert no_id['id']


async def test_tg_simple_inline_search(tg):
    res = await tg._perform_simple_inline_search('q')
    assert res[0]['type'] == 'article'


# ============================================================================
# Google Chat — initialize & status
# ============================================================================

def _gc_event_type(monkeypatch):
    monkeypatch.setattr(gc_mod, 'GoogleChatEventType',
                        SimpleNamespace(MESSAGE='message',
                                        ADDED_TO_SPACE='added_to_space'))


async def test_gc_initialize_missing_services():
    integ = AtomGoogleChatIntegration({})
    integ.google_chat_service = None
    assert await integ.initialize() is False


async def test_gc_initialize_success(gchat, monkeypatch):
    _gc_event_type(monkeypatch)
    gchat.atom_memory = MagicMock()
    gchat.atom_search = MagicMock()
    gchat._start_integration_workers = AsyncMock()
    gchat.google_chat_service.event_handlers = {'message': [],
                                                'added_to_space': []}
    assert await gchat.initialize() is True
    assert gchat.is_initialized
    # memory query raising is swallowed
    gchat.atom_memory.query = AsyncMock(side_effect=RuntimeError('m'))
    await gchat._initialize_unified_data()
    # generic init failure
    gchat._initialize_unified_data = AsyncMock(side_effect=RuntimeError('x'))
    assert await gchat.initialize() is False


async def test_gc_cross_platform_handlers(gchat, monkeypatch):
    _gc_event_type(monkeypatch)
    gchat.google_chat_service.event_handlers = {'message': [],
                                                'added_to_space': []}
    await gchat._setup_cross_platform_handlers()
    assert len(gchat.google_chat_service.event_handlers['message']) == 1
    # and the handlers themselves
    gchat._store_message_in_memory = AsyncMock()
    gchat._index_message_in_search = AsyncMock()
    gchat._trigger_workflows = AsyncMock()
    await gchat._handle_google_chat_message_cross_platform({'a': 1})
    gchat._update_workspace_cross_platform = AsyncMock()
    await gchat._handle_google_chat_space_event_cross_platform({'a': 1})
    gchat._trigger_workflows.assert_awaited()


async def test_gc_service_status(gchat):
    status = await gchat.get_service_status()
    assert status['status'] == 'active'
    gchat.google_chat_service = None
    assert (await gchat.get_service_status())['status'] == 'inactive'


# ============================================================================
# Google Chat — unified workspaces/channels/messages
# ============================================================================

async def test_gc_unified_workspaces(gchat):
    gchat.google_chat_service.get_spaces = AsyncMock(
        return_value=[gc_space('S1'), gc_space('S2', active=False)])
    ws = await gchat.get_unified_workspaces('user1')
    assert len(ws) == 2
    assert ws[0]['platform'] == 'Google Chat'
    assert ws[1]['status'] == 'disconnected'
    assert gchat.active_spaces[0].space_id == 'S1'
    gchat.google_chat_service.get_spaces = AsyncMock(side_effect=RuntimeError('x'))
    assert await gchat.get_unified_workspaces('u') == []


async def test_gc_unified_channels(gchat):
    gchat.active_spaces = [gc_space('S1')]
    chans = await gchat.get_unified_channels('google_chat_S1', 'u')
    assert chans[0]['name'] == 'Space One' and chans[0]['is_private'] is False
    assert await gchat.get_unified_channels('slack_X', 'u') == []
    assert await gchat.get_unified_channels('google_chat_NOPE', 'u') == []


async def test_gc_send_unified_message(gchat):
    gchat.atom_memory = MagicMock()
    gchat.atom_search = MagicMock()
    gchat.atom_workflow = MagicMock()
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': True, 'message_id': 'm1'})
    res = await gchat.send_unified_message(
        'google_chat_S1', 'google_chat_S1', 'hello',
        options={'thread_id': 't', 'message_format': 'TEXT', 'card_v2': []})
    assert res['ok'] is True
    # failure passthrough
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await gchat.send_unified_message('w', 'google_chat_S1', 'x'))['error'] == 'denied'
    # unsupported platform
    assert (await gchat.send_unified_message('w', 'slack_c', 'x'))['error'] == 'Unsupported platform'
    # exception
    gchat.google_chat_service.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.send_unified_message('w', 'google_chat_S1', 'x'))['ok'] is False


async def test_gc_get_unified_messages(gchat):
    gchat.google_chat_service.get_space_messages = AsyncMock(
        return_value=[gc_message('M1'), gc_message('M2')])
    msgs = await gchat.get_unified_messages('google_chat_S1', 'google_chat_S1',
                                            limit=10)
    assert len(msgs) == 2
    m = msgs[0]
    assert m['user_id'] == 'google_chat_U1'
    assert m['mentions'][0]['id'] == 'users/U1'
    assert m['mentions'][0]['name'] == 'Alice'
    assert m['attachments'][0]['content_type'] == 'application/pdf'
    assert m['files'][0]['type'] == 'google_chat_file'
    assert m['reactions'][0]['count'] == 2
    assert m['metadata']['is_bot_message'] is False
    # non-google channel -> empty
    assert await gchat.get_unified_messages('w', 'slack_c') == []
    # exception
    gchat.google_chat_service.get_space_messages = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await gchat.get_unified_messages('w', 'google_chat_S1') == []


async def test_gc_unified_search(gchat):
    gchat.google_chat_service.search_messages = AsyncMock(
        return_value={'ok': True, 'messages': [gc_message(with_integration_data=True)]})
    res = await gchat.unified_search('deploy', channel_id='google_chat_S1',
                                     options={'limit': 5})
    assert res and res[0]['relevance_score'] == 0.9
    assert 'highlights' in res[0]
    # not-ok
    gchat.google_chat_service.search_messages = AsyncMock(
        return_value={'ok': False})
    assert await gchat.unified_search('q', channel_id='google_chat_S1') == []
    # no channel
    assert await gchat.unified_search('q') == []
    # exception
    gchat.google_chat_service.search_messages = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await gchat.unified_search('q', channel_id='google_chat_S1') == []


# ============================================================================
# Google Chat — workflows / analytics
# ============================================================================

async def test_gc_create_unified_workflow(gchat):
    res = await gchat.create_unified_workflow(
        {'triggers': [{'platform': 'google_chat'}], 'actions': []})
    assert res['ok'] is True
    res = await gchat.create_unified_workflow(
        {'triggers': [], 'actions': [{'action': 'google_chat_message'}]})
    assert res['ok'] is True
    # not involved, workflow service present
    gchat.atom_workflow = MagicMock()
    gchat.atom_workflow.create_workflow = AsyncMock(return_value={'ok': True})
    assert (await gchat.create_unified_workflow({'triggers': []}))['ok'] is True
    # not involved, no workflow service
    gchat.atom_workflow = None
    assert (await gchat.create_unified_workflow({'triggers': []}))['error']
    gchat.atom_workflow = MagicMock()
    gchat.atom_workflow.create_workflow = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.create_unified_workflow({'triggers': []}))['ok'] is False


async def test_gc_get_unified_analytics(gchat):
    gchat.google_chat_analytics = MagicMock()
    gchat.google_chat_analytics.get_analytics = AsyncMock(
        return_value=[SimpleNamespace(timestamp=DT, value=5,
                                      dimensions={'a': 1}, metadata={})])
    res = await gchat.get_unified_analytics('message_volume', '7d',
                                            workspace_id='google_chat_S1')
    assert res['total_points'] == 1
    gchat.google_chat_analytics = None
    assert (await gchat.get_unified_analytics('m', 't'))['total_points'] == 0
    gchat.google_chat_analytics = MagicMock()
    gchat.google_chat_analytics.get_analytics = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await gchat.get_unified_analytics('m', 't'))['ok'] is False


# ============================================================================
# Google Chat — memory / search / workflow plumbing
# ============================================================================

async def test_gc_store_index_trigger(gchat):
    gchat.atom_memory = None
    gchat.atom_search = None
    gchat.atom_workflow = None
    await gchat._store_message_in_memory({'message_id': 'm'}, 'google_chat')
    await gchat._index_message_in_search({'message_id': 'm'}, 'google_chat')
    await gchat._trigger_workflows({'a': 1}, 'evt')
    gchat.atom_memory = MagicMock()
    gchat.atom_memory.store = AsyncMock()
    await gchat._store_message_in_memory({'message_id': 'm', 'text': 'hi'},
                                         'google_chat', {'x': 1})
    gchat.atom_memory.store.assert_awaited_once()
    gchat.atom_search = MagicMock()
    gchat.atom_search.index = AsyncMock()
    await gchat._index_message_in_search({'message_id': 'm'}, 'google_chat')
    gchat.atom_search.index.assert_awaited_once()
    gchat.atom_workflow = MagicMock()
    gchat.atom_workflow.trigger_workflows = AsyncMock()
    await gchat._trigger_workflows({'a': 1}, 'evt', {'o': 1})
    gchat.atom_workflow.trigger_workflows.assert_awaited_once()
    # exceptions swallowed
    gchat.atom_memory.store = AsyncMock(side_effect=RuntimeError('x'))
    gchat.atom_search.index = AsyncMock(side_effect=RuntimeError('x'))
    gchat.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError('x'))
    await gchat._store_message_in_memory({}, 'google_chat')
    await gchat._index_message_in_search({}, 'google_chat')
    await gchat._trigger_workflows({}, 'evt')


def test_gc_converters(gchat):
    assert gchat._convert_google_chat_reactions(
        [{'emoji': '👍', 'count': 3}]) == [{'emoji': '👍', 'count': 3,
                                           'user_ids': []}]
    atts = gchat._convert_google_chat_attachments(
        [{'name': 'a', 'title': 't', 'contentType': 'text/plain'}])
    assert atts[0]['download_url'] is None and atts[0]['size'] == 0
    mentions = gchat._convert_google_chat_mentions(
        [{'type': 'other'}, {'type': 'user_mention',
                             'userMention': {'name': 'u', 'displayName': 'd'}}])
    assert len(mentions) == 1
    files = gchat._convert_google_chat_files(
        [{'name': 'a', 'title': 'img', 'contentType': 'image/png'}])
    assert files[0]['platform'] == 'Google Chat'
    assert gchat._convert_google_chat_files(
        [{'contentType': 'text/plain'}]) == []


def test_gc_search_highlights(gchat):
    out = gchat._generate_search_highlights('the quick brown fox jumps', 'fox')
    assert out and 'fox' in out[0]
    assert gchat._generate_search_highlights('no match here', 'zzz') == []


def test_gc_get_space_by_id(gchat):
    gchat.active_spaces = [gc_space('S1')]
    assert gchat._get_space_by_id('S1').space_id == 'S1'
    assert gchat._get_space_by_id('NOPE') is None
    gchat.google_chat_service = None
    assert gchat._get_space_by_id('NOPE') is None


# ============================================================================
# Google Chat — workspace sync
# ============================================================================

async def test_gc_update_workspace_no_sync(gchat):
    gchat.workspace_sync = None
    await gchat._update_workspace_cross_platform({'space': {}}, 'google_chat')


async def test_gc_update_workspace_existing(gchat):
    gchat.workspace_sync = MagicMock()
    gchat.workspace_sync.propagate_change = AsyncMock()
    gchat.db = MagicMock()
    existing = SimpleNamespace(id=1)
    gchat.db.query.return_value.filter.return_value.first.return_value = existing
    await gchat._update_workspace_cross_platform(
        {'type': 'SPACE_UPDATED', 'space': {'name': 'spaces/S1'}}, 'google_chat')
    gchat.workspace_sync.propagate_change.assert_awaited_once()
    # member events & default branch
    for evt in ('MEMBER_ADDED', 'MEMBER_REMOVED', 'SETTINGS_UPDATED', 'OTHER'):
        await gchat._update_workspace_cross_platform(
            {'type': evt, 'space': {'name': 'spaces/S1'}}, 'google_chat')


async def test_gc_update_workspace_create(gchat):
    gchat.workspace_sync = MagicMock()
    gchat.workspace_sync.propagate_change = AsyncMock()
    gchat.workspace_sync.create_unified_workspace.return_value = SimpleNamespace(id=2)
    gchat.db = MagicMock()
    gchat.db.query.return_value.filter.return_value.first.return_value = None
    await gchat._update_workspace_cross_platform(
        {'type': 'RENAME_SPACE', 'space': {'name': 'spaces/S2'}}, 'google_chat')
    gchat.workspace_sync.create_unified_workspace.assert_called_once()
    # get-or-create returns None when db blows up
    gchat.db.query.side_effect = RuntimeError('db')
    res = await gchat._get_or_create_unified_workspace('S3', 'n')
    assert res is None
    # propagate raising -> swallowed
    gchat.workspace_sync.propagate_change = AsyncMock(side_effect=RuntimeError('x'))
    gchat.db.query.side_effect = None
    gchat.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id=1)
    await gchat._update_workspace_cross_platform(
        {'type': 'MEMBER_ADDED', 'space': {'name': 'spaces/S1'}}, 'google_chat')


# ============================================================================
# Google Chat — background workers
# ============================================================================

async def _run_and_cancel(coro):
    task = asyncio.create_task(coro)
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_gc_workers(gchat):
    await _run_and_cancel(gchat._google_chat_message_ingestion_worker())
    await _run_and_cancel(gchat._google_chat_event_processing_worker())
    # indexing worker with services present
    gchat.atom_memory = MagicMock()
    gchat.atom_memory.query = AsyncMock(return_value=[{'id': 'm1', 'text': 't'}])
    gchat.atom_memory.update = AsyncMock()
    gchat.atom_search = MagicMock()
    gchat.atom_search.index = AsyncMock()
    await _run_and_cancel(gchat._unified_search_indexing_worker())
    gchat.atom_memory.update.assert_awaited()


# ============================================================================
# Google Chat — OAuth
# ============================================================================

async def test_gc_oauth_url(gchat, monkeypatch):
    monkeypatch.setenv('GOOGLE_CHAT_CLIENT_ID', 'cid')
    url = await gchat.get_oauth_url(
        'https://cb', state='st', include_granted_scopes=True,
        login_hint='u@x.com')
    assert 'accounts.google.com' in url and 'state=st' in url
    monkeypatch.delenv('GOOGLE_CHAT_CLIENT_ID')
    with pytest.raises(ValueError):
        await gchat.get_oauth_url('https://cb')


async def test_gc_oauth_callback_success(gchat, monkeypatch):
    monkeypatch.setenv('GOOGLE_CHAT_CLIENT_ID', 'cid')
    monkeypatch.setenv('GOOGLE_CHAT_CLIENT_SECRET', 'sec')
    resp = MagicMock()
    resp.json.return_value = {'access_token': 'at', 'refresh_token': 'rt',
                              'expires_in': 3600}
    resp.raise_for_status = MagicMock()
    cls = MagicMock()
    cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
    monkeypatch.setattr('httpx.AsyncClient', cls)
    res = await gchat.handle_oauth_callback('code', state='st',
                                            redirect_uri='https://cb')
    assert res['success'] is True and res['access_token'] == 'at'
    # http error
    resp.raise_for_status = MagicMock(side_effect=RuntimeError('http 500'))
    assert (await gchat.handle_oauth_callback('c', state='s'))['success'] is False
    # missing state
    assert (await gchat.handle_oauth_callback('c'))['success'] is False
    # missing creds
    monkeypatch.delenv('GOOGLE_CHAT_CLIENT_SECRET')
    assert (await gchat.handle_oauth_callback('c', state='s'))['success'] is False


async def test_gc_refresh_token(gchat, monkeypatch):
    monkeypatch.setenv('GOOGLE_CHAT_CLIENT_ID', 'cid')
    monkeypatch.setenv('GOOGLE_CHAT_CLIENT_SECRET', 'sec')
    resp = MagicMock()
    resp.json.return_value = {'access_token': 'at2', 'expires_in': 1000}
    resp.raise_for_status = MagicMock()
    cls = MagicMock()
    cls.return_value.__aenter__.return_value.post = AsyncMock(return_value=resp)
    monkeypatch.setattr('httpx.AsyncClient', cls)
    res = await gchat.refresh_access_token('rt')
    assert res['success'] is True and res['refresh_token'] == 'rt'
    resp.raise_for_status = MagicMock(side_effect=RuntimeError('x'))
    assert (await gchat.refresh_access_token('rt'))['success'] is False
    monkeypatch.delenv('GOOGLE_CHAT_CLIENT_SECRET')
    assert (await gchat.refresh_access_token('rt'))['success'] is False


# ============================================================================
# Google Chat — cards & dialogs
# ============================================================================

async def test_gc_send_card(gchat):
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': True, 'message_id': 'm1'})
    res = await gchat.send_card('spaces/S1', message='hi',
                                card={'cardHeader': {'title': 't'}})
    assert res['success'] is True and res['message_name'] == 'm1'
    # built from components
    res = await gchat.send_card('spaces/S1', header={'title': 'h'},
                                sections=[{'widgets': []}],
                                widgets=[{'textParagraph': {'text': 'x'}}],
                                thread_key='tk')
    assert res['success'] is True
    # multiple cards
    res = await gchat.send_card('spaces/S1', cards=[{'a': 1}, {'b': 2}])
    assert res['success'] is True
    # service reports failure
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await gchat.send_card('spaces/S1', card={'a': 1}))['error'] == 'denied'
    # no service -> simulated
    gchat.google_chat_service = None
    res = await gchat.send_card('spaces/S1')
    assert res['success'] is True and res.get('note')
    # exception
    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.send_card('spaces/S1'))['success'] is False


async def test_gc_update_card_and_dialog(gchat):
    gchat.google_chat_service.update_message = AsyncMock(return_value={'ok': True})
    res = await gchat.update_card('spaces/S1', 'messages/M1')
    assert res['success'] is True
    gchat.google_chat_service.update_message = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await gchat.update_card('s', 'm'))['success'] is False
    gchat.google_chat_service = None
    assert (await gchat.update_card('s', 'm')).get('note')

    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.open_dialog = AsyncMock(return_value={'ok': True})
    res = await gchat.open_dialog('spaces/S1', {'body': {}})
    assert res['success'] is True
    gchat.google_chat_service.open_dialog = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.open_dialog('s', {}))['success'] is False
    gchat.google_chat_service = None
    assert (await gchat.open_dialog('s', {})).get('note')


# ============================================================================
# Google Chat — space management
# ============================================================================

async def test_gc_create_space(gchat):
    gchat.google_chat_service.create_space = AsyncMock(
        return_value={'ok': True, 'space_name': 'spaces/N1'})
    gchat.add_space_members = AsyncMock(
        return_value={'success': True, 'added_count': 1})
    res = await gchat.create_space('New', description='d', members=['a@x.com'])
    assert res['success'] is True and res['members_added'] == 1
    gchat.google_chat_service.create_space = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await gchat.create_space('New'))['error'] == 'denied'
    gchat.google_chat_service = None
    assert (await gchat.create_space('New')).get('note')
    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.create_space = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.create_space('New'))['success'] is False


async def test_gc_list_spaces(gchat):
    gchat.google_chat_service.get_spaces = AsyncMock(
        return_value={'ok': True, 'spaces': [{'space_name': 'spaces/S1',
                                              'display_name': 'One',
                                              'type': 'ROOM', 'member_count': 2,
                                              'threaded': True}]})
    res = await gchat.list_spaces()
    assert res['success'] is True and res['count'] == 1
    gchat.google_chat_service.get_spaces = AsyncMock(
        return_value={'ok': False})
    assert (await gchat.list_spaces())['spaces'] == []
    gchat.google_chat_service = None
    assert (await gchat.list_spaces())['spaces'] == []
    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.get_spaces = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.list_spaces())['success'] is False


async def test_gc_space_info(gchat):
    gchat.google_chat_service.get_space = AsyncMock(
        return_value={'ok': True, 'space': {'space_name': 'spaces/S1',
                                            'display_name': 'One',
                                            'description': 'd', 'type': 'ROOM',
                                            'member_count': 2, 'threaded': True,
                                            'created_at': 't'}})
    res = await gchat.get_space_info('spaces/S1')
    assert res['success'] is True and res['display_name'] == 'One'
    gchat.google_chat_service.get_space = AsyncMock(return_value={'ok': False})
    assert (await gchat.get_space_info('spaces/S1')).get('note')
    gchat.google_chat_service = None
    assert (await gchat.get_space_info('spaces/S1'))['name'] == 'spaces/S1'
    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.get_space = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.get_space_info('s'))['success'] is False


async def test_gc_space_members(gchat):
    gchat.google_chat_service.add_member = AsyncMock(return_value={'ok': True})
    res = await gchat.add_space_members('spaces/S1', ['a@x.com', 'b@x.com'])
    assert res['added_count'] == 2
    gchat.google_chat_service.add_member = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await gchat.add_space_members('s', ['a']))['success'] is False
    gchat.google_chat_service = None
    assert (await gchat.add_space_members('s', ['a']))['added_count'] == 0

    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.remove_member = AsyncMock(return_value={'ok': True})
    assert (await gchat.remove_space_members('s', ['a']))['removed_count'] == 1
    gchat.google_chat_service.remove_member = AsyncMock(
        side_effect=RuntimeError('x'))
    assert (await gchat.remove_space_members('s', ['a']))['success'] is False
    gchat.google_chat_service = None
    assert (await gchat.remove_space_members('s', ['a']))['removed_count'] == 0


async def test_gc_set_space_webhook(gchat):
    res = await gchat.set_space_webhook('spaces/S1', 'https://hook', state='s')
    assert res['success'] is True


# ============================================================================
# Google Chat — messages & files
# ============================================================================

async def test_gc_send_message(gchat):
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': True, 'message_id': 'm9'})
    res = await gchat.send_message('spaces/S1', 'hello', thread_key='t')
    assert res['success'] is True and res['message_name'] == 'm9'
    gchat.google_chat_service.send_message = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await gchat.send_message('s', 'x'))['error'] == 'denied'
    gchat.google_chat_service = None
    assert (await gchat.send_message('s', 'x')).get('note')
    gchat.google_chat_service = MagicMock()
    gchat.google_chat_service.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await gchat.send_message('s', 'x'))['success'] is False


async def test_gc_upload_file(gchat, tmp_path):
    f = tmp_path / 'a.txt'
    f.write_text('content')
    gchat.google_chat_service.upload_file = AsyncMock(
        return_value={'ok': True, 'file_name': 'files/F1'})
    res = await gchat.upload_file('spaces/S1', file_path=str(f))
    assert res['success'] is True
    res = await gchat.upload_file('spaces/S1', content='abc', filename='c.txt',
                                  mime_type='text/plain')
    assert res['success'] is True and res['mime_type'] == 'text/plain'
    # neither path nor content
    assert (await gchat.upload_file('s'))['success'] is False
    # service failure
    gchat.google_chat_service.upload_file = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await gchat.upload_file('s', content='x', filename='f'))['error'] == 'denied'
    # simulated
    gchat.google_chat_service = None
    assert (await gchat.upload_file('s', content='x', filename='f')).get('note')
    # exception (unreadable file)
    gchat.google_chat_service = MagicMock()
    assert (await gchat.upload_file('s', file_path='/nonexistent/x'))['success'] is False
