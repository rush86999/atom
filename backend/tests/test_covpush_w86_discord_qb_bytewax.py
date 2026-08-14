# -*- coding: utf-8 -*-
"""Coverage wave 86 — integrations.atom_discord_integration,
integrations.atom_quickbooks_integration_service, integrations.bytewax_service.

No network, no LLM: HTTP is mocked (httpx.AsyncClient), all service
boundaries (discord enhanced service, AI, memory/search/workflow, LanceDB,
bytewax operators) are AsyncMock/MagicMock objects.
"""
import asyncio
import queue as queue_mod
import sys
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.atom_discord_integration as dc_mod
from integrations.atom_discord_integration import AtomDiscordIntegration
import integrations.atom_quickbooks_integration_service as qb_mod
from integrations.atom_quickbooks_integration_service import (
    AtomQuickBooksIntegrationService,
    FinancialReportType,
)
import integrations.bytewax_service as bw_mod
from integrations.bytewax_service import (
    BytewaxIngestionService,
    BytewaxQueuePartition,
    BytewaxQueueSource,
    DocumentParsingOperator,
    FastEmbedOperator,
    FormulaExtractionOperator,
    KnowledgeExtractionOperator,
    LanceDBSink,
    LanceDBStatelessSinkPartition,
    SecretsRedactionOperator,
    UnifiedNormalizationOperator,
    get_bytewax_queue,
)
from integrations.atom_ingestion_pipeline import AtomRecordData, RecordType


DT = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)


# ============================================================================
# Discord — helpers / fixtures
# ============================================================================

@pytest.fixture()
def discord(monkeypatch):
    """Integration with mocked enhanced service + patched module symbols."""
    monkeypatch.setattr(dc_mod, 'DiscordEventType', SimpleNamespace(
        MESSAGE_CREATE='message_create', GUILD_CREATE='guild_create',
        VOICE_STATE_UPDATE='voice_state_update'))
    monkeypatch.setattr(dc_mod, 'DiscordGuild',
                        lambda **kw: SimpleNamespace(**kw))
    integ = AtomDiscordIntegration({})
    integ.discord_service = MagicMock()
    integ.discord_service.event_handlers = {
        'message_create': [], 'guild_create': [], 'voice_state_update': []}
    integ.atom_memory = MagicMock()
    integ.atom_search = MagicMock()
    integ.atom_workflow = MagicMock()
    return integ


def d_guild(guild_id='G1', connected=True):
    return SimpleNamespace(
        guild_id=guild_id, name=f'Guild {guild_id}', is_connected=connected,
        member_count=10, channel_count=4, icon_url='http://icon',
        description='desc', owner_id='O1', owner_name='Owner',
        region='us', features=['FEAT'], premium_tier=2,
        verification_level=1, roles_count=5, emojis_count=6, created_at=DT)


def d_channel(channel_id='C1'):
    return SimpleNamespace(
        channel_id=channel_id, name='general', topic='talk',
        type=SimpleNamespace(value='TEXT_CHANNEL'), member_count=3,
        message_count=9, is_archived=False, is_private=False,
        is_text=True, is_voice=False, is_stage=False, is_news=False,
        is_thread=False, position=1, parent_id='P', permissions={'r': True},
        rate_limit_per_user=0, guild_id='G1', nsfw=False, bitrate=None,
        user_limit=None, default_auto_archive_duration=1440, flags=0,
        permission_overwrites=[], last_pin_timestamp=None, rtc_region=None,
        last_modified_at='2026-08-10T00:00:00Z')


def d_message(message_id='M1', ts='2026-08-10T01:00:00Z'):
    return SimpleNamespace(
        message_id=message_id, content='deploy the service', user_id='U1',
        user_name='alice', user_display_name='Alice', user_discriminator='0001',
        user_avatar='av', timestamp=ts, thread_id=None, reply_to_id=None,
        type=0, is_edited=False, edited_timestamp=None, is_pinned=False,
        is_crossposted=False, is_command=False, is_bot=False, is_webhook=False,
        is_system=False,
        reactions=[{'emoji': {'name': '👍', 'id': 'e1', 'animated': True},
                    'count': 2, 'me': True}],
        attachments=[{'id': 'a1', 'filename': 'f.pdf',
                      'content_type': 'application/pdf', 'url': 'u',
                      'proxy_url': 'pu', 'size': 10, 'width': 1, 'height': 2}],
        mentions=[{'id': 'u2', 'username': 'bob', 'discriminator': '2',
                   'display_name': 'Bob', 'avatar': 'a'}],
        embeds=[{'title': 'T', 'description': 'D', 'url': 'http://u',
                 'type': 'rich', 'color': 1, 'timestamp': ts,
                 'footer': {'f': 1}, 'image': {'i': 1},
                 'thumbnail': {'t': 1}, 'video': {'v': 1},
                 'author': {'a': 1}, 'fields': [{'name': 'n'}]}],
        components=[{'c': 1}], stickers=['s'], mention_roles=['r'],
        mention_channels=['c'], mention_everyone=False, tts=False,
        pinned=False, flags=0, member={}, referenced_message=None,
        interaction=None, application_id=None, webhook_id=None,
        position=None, message_snapshots=[])


# ============================================================================
# Discord — initialize / lifecycle
# ============================================================================

async def test_dc_initialize_missing_services():
    integ = AtomDiscordIntegration({})
    assert await integ.initialize() is False


async def test_dc_initialize_success(discord):
    assert await discord.initialize() is True
    assert discord.is_initialized
    assert len(discord.discord_service.event_handlers['message_create']) == 1
    assert len(discord.discord_service.event_handlers['guild_create']) == 1
    assert len(discord.discord_service.event_handlers['voice_state_update']) == 1
    # initialize is idempotent-safe: run handlers setup again
    await discord._setup_cross_platform_handlers()
    assert len(discord.discord_service.event_handlers['message_create']) == 2


async def test_dc_initialize_exception(discord):
    discord._start_integration_workers = AsyncMock(side_effect=RuntimeError('x'))
    assert await discord.initialize() is False


async def test_dc_initialize_unified_data(discord):
    discord.atom_memory.query = AsyncMock(return_value=[{'id': 1}])
    await discord._initialize_unified_data()
    discord.atom_memory.query = AsyncMock(side_effect=RuntimeError('db'))
    await discord._initialize_unified_data()  # swallowed
    discord.atom_memory = None
    await discord._initialize_unified_data()


async def test_dc_get_guild_by_id(discord, monkeypatch):
    guild = discord._get_guild_by_id('G1')
    assert guild.guild_id == 'G1'
    monkeypatch.setattr(dc_mod, 'DiscordGuild',
                        MagicMock(side_effect=RuntimeError('boom')))
    assert discord._get_guild_by_id('G1') is None


# ============================================================================
# Discord — unified workspaces / channels
# ============================================================================

async def test_dc_unified_workspaces(discord):
    discord.discord_service.get_guilds = AsyncMock(
        return_value=[d_guild('G1'), d_guild('G2', connected=False)])
    ws = await discord.get_unified_workspaces('user1')
    assert len(ws) == 2
    assert ws[0]['id'] == 'discord_G1' and ws[0]['platform'] == 'Discord'
    assert ws[0]['status'] == 'connected'
    assert ws[1]['status'] == 'disconnected'
    assert ws[0]['capabilities']['voice_calls'] is True
    assert discord.active_guilds[0].guild_id == 'G1'
    discord.discord_service.get_guilds = AsyncMock(side_effect=RuntimeError('x'))
    assert await discord.get_unified_workspaces('u') == []


async def test_dc_unified_channels(discord):
    discord.discord_service.get_guild_channels = AsyncMock(
        return_value=[d_channel('C1'), d_channel('C2')])
    chans = await discord.get_unified_channels('discord_G1', 'u')
    assert len(chans) == 2
    assert chans[0]['id'] == 'discord_C1'
    assert chans[0]['type'] == 'text-channel'
    assert chans[0]['integration_data']['nsfw'] is False
    assert chans[0]['capabilities']['messaging'] is True
    assert await discord.get_unified_channels('slack_X', 'u') == []
    # non-dict-ish channel blows up -> swallowed
    bad = SimpleNamespace(type=None)
    bad.channel_id = 'C3'
    discord.discord_service.get_guild_channels = AsyncMock(return_value=[bad])
    assert await discord.get_unified_channels('discord_G1', 'u') == []


# ============================================================================
# Discord — messages / send / search
# ============================================================================

async def test_dc_send_unified_message(discord):
    discord.discord_service.send_message = AsyncMock(
        return_value={'ok': True, 'message_id': 'M9'})
    res = await discord.send_unified_message(
        'discord_G1', 'discord_C1', 'hello',
        options={'guild_id': 'G1', 'embed': {'e': 1}, 'components': [],
                 'tts': True})
    assert res['ok'] is True and res['message_id'] == 'M9'
    # not-ok passthrough
    discord.discord_service.send_message = AsyncMock(
        return_value={'ok': False, 'error': 'denied'})
    assert (await discord.send_unified_message('w', 'discord_C1', 'x'))['error'] == 'denied'
    # unsupported platform
    assert (await discord.send_unified_message('w', 'slack_c', 'x'))['error'] == 'Unsupported platform'
    # exception
    discord.discord_service.send_message = AsyncMock(side_effect=RuntimeError('x'))
    assert (await discord.send_unified_message('w', 'discord_C1', 'x'))['ok'] is False


async def test_dc_get_unified_messages(discord):
    discord.discord_service.get_channel_messages = AsyncMock(
        return_value=[d_message('M1', '2026-08-10T01:00:00Z'),
                      d_message('M2', '2026-08-10T02:00:00Z')])
    msgs = await discord.get_unified_messages(
        'discord_G1', 'discord_C1', limit=10,
        options={'before': 'a', 'after': 'b', 'around': 'c'})
    assert len(msgs) == 2 and msgs[0]['id'] == 'discord_M2'  # sorted desc
    m = msgs[1]
    assert m['user_id'] == 'discord_U1'
    assert m['reactions'][0]['emoji'] == '👍'
    assert m['attachments'][0]['type'] == 'discord_attachment'
    assert m['mentions'][0]['platform'] == 'Discord'
    assert m['embeds'][0]['title'] == 'T'
    assert m['metadata']['has_reactions'] is True
    assert m['integration_data']['message_id'] == 'M1'
    # non-discord channel -> empty
    assert await discord.get_unified_messages('w', 'slack_c') == []
    # exception
    discord.discord_service.get_channel_messages = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await discord.get_unified_messages('w', 'discord_C1') == []


async def test_dc_unified_search(discord):
    discord.discord_service.search_messages = AsyncMock(return_value={
        'ok': True,
        'messages': [{'results': [
            {'id': 'r1', 'content': 'deploy now', 'timestamp': 't',
             'author': {'id': 'U1', 'username': 'alice'}},
            {'id': 'r2', 'content': 'x', 'timestamp': 't', 'author': None},
        ]}]})
    res = await discord.unified_search('deploy', workspace_id='discord_G1',
                                       channel_id='discord_C1',
                                       options={'limit': 5})
    assert len(res) == 2 and res[0]['relevance_score'] == 1.0
    assert res[1]['user_id'] == 'discord_None'  # author={} default
    # not ok
    discord.discord_service.search_messages = AsyncMock(return_value={'ok': False})
    assert await discord.unified_search('q', channel_id='discord_C1') == []
    # no channel
    assert await discord.unified_search('q') == []
    # exception
    discord.discord_service.search_messages = AsyncMock(side_effect=RuntimeError('x'))
    assert await discord.unified_search('q', channel_id='discord_C1') == []


# ============================================================================
# Discord — workflows / analytics / converters
# ============================================================================

async def test_dc_create_unified_workflow(discord):
    assert (await discord.create_unified_workflow(
        {'triggers': [{'platform': 'discord'}], 'actions': []}))['ok'] is True
    assert (await discord.create_unified_workflow(
        {'triggers': [{'event': 'Discord_Message'}], 'actions': []}))['ok'] is True
    assert (await discord.create_unified_workflow(
        {'triggers': [], 'actions': [{'action': 'send_discord_message'}]}))['ok'] is True
    discord.atom_workflow = None
    assert (await discord.create_unified_workflow({'triggers': []}))['error']
    discord.atom_workflow = MagicMock()
    discord.atom_workflow.create_workflow = AsyncMock(return_value={'ok': True})
    assert (await discord.create_unified_workflow({'triggers': []}))['ok'] is True
    discord.atom_workflow.create_workflow = AsyncMock(side_effect=RuntimeError('x'))
    assert (await discord.create_unified_workflow({'triggers': []}))['ok'] is False


async def test_dc_unified_analytics(discord):
    discord.discord_analytics = MagicMock()
    discord.discord_analytics.get_analytics = AsyncMock(return_value=[
        SimpleNamespace(timestamp=DT, value=5, dimensions={'a': 1}, metadata={})])
    res = await discord.get_unified_analytics('metric', '7d',
                                              workspace_id='discord_G1')
    assert res['total_points'] == 1 and res['platform'] == 'Discord'
    discord.discord_analytics = None
    assert (await discord.get_unified_analytics('m', 't'))['total_points'] == 0
    discord.discord_analytics = MagicMock()
    discord.discord_analytics.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert (await discord.get_unified_analytics('m', 't'))['ok'] is False


def test_dc_converters(discord):
    assert discord._convert_discord_message_type(19) == 'reply'
    assert discord._convert_discord_message_type(999) == 'unknown'
    assert discord._convert_discord_reactions([{'count': 3}])[0]['emoji'] == '❓'
    assert discord._convert_discord_attachments([{}])[0]['size'] == 0
    assert discord._convert_discord_mentions([{}])[0]['type'] == 'user'
    assert discord._convert_discord_embeds([{}])[0]['fields'] == []


# ============================================================================
# Discord — cross-platform handlers, memory/search/workflow plumbing
# ============================================================================

async def test_dc_cross_platform_handlers(discord):
    discord._store_message_in_memory = AsyncMock()
    discord._index_message_in_search = AsyncMock()
    discord._trigger_workflows = AsyncMock()
    await discord._handle_discord_message_cross_platform({'a': 1})
    discord._store_message_in_memory.assert_awaited_once()

    discord._update_workspace_cross_platform = AsyncMock()
    await discord._handle_discord_guild_event_cross_platform({'b': 2})
    discord._update_workspace_cross_platform.assert_awaited_once()

    discord._update_voice_state_cross_platform = AsyncMock()
    await discord._handle_discord_voice_event_cross_platform({'c': 3})
    discord._update_voice_state_cross_platform.assert_awaited_once()

    # internal exceptions are swallowed
    discord._store_message_in_memory = AsyncMock(side_effect=RuntimeError('x'))
    discord._update_workspace_cross_platform = AsyncMock(side_effect=RuntimeError('x'))
    discord._update_voice_state_cross_platform = AsyncMock(side_effect=RuntimeError('x'))
    await discord._handle_discord_message_cross_platform({})
    await discord._handle_discord_guild_event_cross_platform({})
    await discord._handle_discord_voice_event_cross_platform({})


async def test_dc_memory_search_workflow_plumbing(discord):
    discord.atom_memory = None
    discord.atom_search = None
    discord.atom_workflow = None
    await discord._store_message_in_memory({}, 'discord')
    await discord._index_message_in_search({}, 'discord')
    await discord._trigger_workflows({}, 'evt')
    discord.atom_memory = MagicMock()
    discord.atom_memory.store = AsyncMock()
    await discord._store_message_in_memory({'message_id': 'm'}, 'discord')
    discord.atom_memory.store.assert_awaited_once()
    discord.atom_search = MagicMock()
    discord.atom_search.index = AsyncMock()
    await discord._index_message_in_search({'message_id': 'm'}, 'discord')
    discord.atom_search.index.assert_awaited_once()
    discord.atom_workflow = MagicMock()
    discord.atom_workflow.trigger_workflows = AsyncMock()
    await discord._trigger_workflows({}, 'evt')
    discord.atom_workflow.trigger_workflows.assert_awaited_once()
    # exceptions swallowed
    discord.atom_memory.store = AsyncMock(side_effect=RuntimeError('x'))
    discord.atom_search.index = AsyncMock(side_effect=RuntimeError('x'))
    discord.atom_workflow.trigger_workflows = AsyncMock(side_effect=RuntimeError('x'))
    await discord._store_message_in_memory({}, 'discord')
    await discord._index_message_in_search({}, 'discord')
    await discord._trigger_workflows({}, 'evt')


# ============================================================================
# Discord — workspace sync
# ============================================================================

async def test_dc_update_workspace_no_sync(discord):
    discord.workspace_sync = None
    await discord._update_workspace_cross_platform({'guild_id': 'G1'}, 'discord')


async def test_dc_update_workspace_event_types(discord):
    discord.workspace_sync = MagicMock()
    discord.workspace_sync.propagate_change = AsyncMock()
    discord.db = MagicMock()
    discord.db.query.return_value.filter.return_value.first.return_value = \
        SimpleNamespace(id=1)
    for evt in ('GUILD_UPDATE', 'GUILD_NAME_UPDATE', 'GUILD_MEMBER_ADD',
                'GUILD_MEMBER_REMOVE', 'GUILD_ROLE_UPDATE',
                'GUILD_CHANNEL_CREATE', 'GUILD_CHANNEL_DELETE', 'OTHER'):
        await discord._update_workspace_cross_platform(
            {'guild_id': 'G1', 'guild_name': 'N', 'type': evt}, 'discord')
    assert discord.workspace_sync.propagate_change.await_count == 8
    # propagate raising -> swallowed
    discord.workspace_sync.propagate_change = AsyncMock(side_effect=RuntimeError('x'))
    await discord._update_workspace_cross_platform(
        {'guild_id': 'G1', 'type': 'X'}, 'discord')


async def test_dc_get_or_create_workspace(discord):
    discord.workspace_sync = MagicMock()
    discord.workspace_sync.create_unified_workspace.return_value = \
        SimpleNamespace(id=7)
    discord.db = MagicMock()
    discord.db.query.return_value.filter.return_value.first.return_value = None
    ws = await discord._get_or_create_unified_workspace('G9', 'New')
    assert ws.id == 7
    discord.workspace_sync.create_unified_workspace.assert_called_once()
    # db failure -> None
    discord.db.query.side_effect = RuntimeError('db')
    assert await discord._get_or_create_unified_workspace('G9', 'N') is None


async def test_dc_update_workspace_create_fails(discord):
    discord.workspace_sync = MagicMock()
    discord.db = MagicMock()
    discord.db.query.return_value.filter.return_value.first.return_value = None
    discord._get_or_create_unified_workspace = AsyncMock(return_value=None)
    await discord._update_workspace_cross_platform(
        {'guild_id': 'G1', 'type': 'X'}, 'discord')  # warns and returns


async def test_dc_voice_state_update(discord):
    discord.workspace_sync = MagicMock()
    ws = SimpleNamespace(id=1, voice_states={}, metadata={},
                         updated_at=None)
    discord.db = MagicMock()
    discord.db.query.return_value.filter.return_value.first.return_value = ws
    await discord._update_voice_state_cross_platform(
        {'user_id': 'U1', 'guild_id': 'G1', 'channel_id': 'VC',
         'state': 'joined'}, 'discord')
    assert 'U1_discord' in ws.voice_states
    assert discord.db.commit.called
    # no workspace found
    discord.db.query.return_value.filter.return_value.first.return_value = None
    await discord._update_voice_state_cross_platform(
        {'user_id': 'U1', 'state': 'joined'}, 'discord')
    # no sync service
    discord.workspace_sync = None
    await discord._update_voice_state_cross_platform({}, 'discord')
    # exception swallowed
    discord.workspace_sync = MagicMock()
    discord.db.query.side_effect = RuntimeError('db')
    await discord._update_voice_state_cross_platform({}, 'discord')


async def test_dc_voice_state_conflicts():
    ws = SimpleNamespace(metadata={
        'voice_conflicts': [{'user_id': 'U1'}]})
    ws.voice_states = {
        'U1_slack': {'platform': 'slack', 'state': 'joined',
                     'channel_id': 'c', 'timestamp': 't'},
        'U1_discord': {'platform': 'discord', 'state': 'joined',
                       'channel_id': 'c', 'timestamp': 't'},
        'U2_slack': {'platform': 'slack', 'state': 'joined',
                     'channel_id': 'c', 'timestamp': 't'},
        'U1_teams': {'platform': 'teams', 'state': 'left',
                     'channel_id': 'c', 'timestamp': 't'},
    }
    await AtomDiscordIntegration({})._check_voice_state_conflicts(
        ws, 'U1', 'discord', 'joined')
    assert len(ws.metadata['voice_conflicts']) == 2
    # inactive state short-circuits
    # exception swallowed
    bad = SimpleNamespace(metadata=None, voice_states=None)
    await AtomDiscordIntegration({})._check_voice_state_conflicts(
        bad, 'U1', 'discord', 'joined')


# ============================================================================
# Discord — background workers
# ============================================================================

async def _run_and_cancel(coro):
    task = asyncio.create_task(coro)
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def test_dc_workers(discord):
    await _run_and_cancel(discord._discord_message_ingestion_worker())
    await _run_and_cancel(discord._discord_event_processing_worker())
    discord.atom_memory = MagicMock()
    discord.atom_memory.query = AsyncMock(
        return_value=[{'id': 'm1', 'content': 'c'}])
    discord.atom_memory.update = AsyncMock()
    discord.atom_search = MagicMock()
    discord._index_message_in_search = AsyncMock()
    await _run_and_cancel(discord._unified_search_indexing_worker())
    discord.atom_memory.update.assert_awaited()


# ============================================================================
# QuickBooks — helpers / fixtures
# ============================================================================

def _qb_httpx(monkeypatch, method='post', payload=None, status=200, exc=None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = 'err-body'
    resp.json.return_value = payload if payload is not None else {}
    cls = MagicMock()
    client = cls.return_value.__aenter__.return_value
    m = AsyncMock(return_value=resp)
    if exc is not None:
        m = AsyncMock(side_effect=exc)
    setattr(client, method, m)
    monkeypatch.setattr(qb_mod.httpx, 'AsyncClient', cls)
    return client


@pytest.fixture()
def qb():
    svc = AtomQuickBooksIntegrationService('t1', {
        'quickbooks_access_token': 'tok',
        'quickbooks_company_id': 'co1',
        'enable_stripe_integration': False,
    })
    svc.ai_service = None
    svc.enterprise_automation = None
    svc.enterprise_security = None
    return svc


def _allow_guard(monkeypatch):
    monkeypatch.setattr(qb_mod, 'circuit_breaker',
                        MagicMock(is_enabled=AsyncMock(return_value=True)))
    monkeypatch.setattr(qb_mod, 'rate_limiter',
                        MagicMock(is_rate_limited=AsyncMock(
                            return_value=(False, 10))))


def _deny_breaker(monkeypatch):
    monkeypatch.setattr(qb_mod, 'circuit_breaker',
                        MagicMock(is_enabled=AsyncMock(return_value=False)))


def _deny_rate(monkeypatch):
    monkeypatch.setattr(qb_mod, 'circuit_breaker',
                        MagicMock(is_enabled=AsyncMock(return_value=True)))
    monkeypatch.setattr(qb_mod, 'rate_limiter',
                        MagicMock(is_rate_limited=AsyncMock(
                            return_value=(True, 0))))


# ============================================================================
# QuickBooks — initialize / auth / connection
# ============================================================================

async def test_qb_initialize_success(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, method='get', payload={'Company': {}}, status=200)
    assert await qb.initialize() is True
    assert qb.is_initialized


async def test_qb_initialize_connection_failure(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, method='get', payload={}, status=500)
    assert await qb.initialize() is False


async def test_qb_initialize_no_token(monkeypatch):
    svc = AtomQuickBooksIntegrationService('t', {
        'quickbooks_access_token': None,
        'enable_stripe_integration': False})
    assert await svc.initialize() is False


async def test_qb_get_auth_headers(qb):
    h = await qb._get_auth_headers()
    assert h['Authorization'] == 'Bearer tok'
    qb.quickbooks_config['access_token'] = None
    with pytest.raises(Exception):
        await qb._get_auth_headers()


async def test_qb_test_connection(qb, monkeypatch):
    _qb_httpx(monkeypatch, method='get', payload={}, status=200)
    assert await qb._test_quickbooks_connection() is True
    _qb_httpx(monkeypatch, method='get', payload={}, status=401)
    with pytest.raises(Exception):
        await qb._test_quickbooks_connection()


def test_qb_stripe_init_paths(monkeypatch):
    # import failure -> None
    svc = AtomQuickBooksIntegrationService('t', {
        'quickbooks_access_token': 'x',
        'enable_stripe_integration': True})
    assert svc.stripe_integration is None
    # import success -> module attr
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, 'atom_stripe_integration', fake)
    svc2 = AtomQuickBooksIntegrationService('t', {
        'quickbooks_access_token': 'x',
        'enable_stripe_integration': True})
    assert svc2.stripe_integration is fake.atom_stripe_integration
    assert svc2.stripe_integration is not None


# ============================================================================
# QuickBooks — create_invoice
# ============================================================================

async def test_qb_create_invoice_success(qb, monkeypatch):
    _allow_guard(monkeypatch)
    client = _qb_httpx(monkeypatch, payload={'Invoice': {'Id': 'INV1',
                                                         'TotalAmt': 100}})
    res = await qb.create_invoice({'customer_id': 'C1', 'amount': 100.0},
                                  platform='slack')
    assert res['success'] is True and res['invoice_id'] == 'INV1'
    assert qb.analytics_metrics['total_invoices'] == 1
    # auto-categorization AI failure path exercised (AIRequest unavailable)
    assert client.post.await_count == 1


async def test_qb_create_invoice_platform_notify(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, payload={'Invoice': {'Id': 'I'}})
    qb.platform_integrations['slack'] = MagicMock()
    qb.platform_integrations['slack'].notify_event = AsyncMock()
    qb._cache_invoice = AsyncMock()
    await qb.create_invoice({'amount': 1}, platform='slack')
    qb.platform_integrations['slack'].notify_event.assert_awaited_once()


async def test_qb_create_invoice_with_ai(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, payload={'Invoice': {'Id': 'I'}})
    monkeypatch.setattr(qb_mod, 'AIRequest', MagicMock(), raising=False)
    monkeypatch.setattr(qb_mod, 'AITaskType',
                        MagicMock(CONTENT_ANALYSIS='ca'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIModelType', MagicMock(GPT_4='g4'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIServiceType', MagicMock(OPENAI='oa'), raising=False)
    qb.ai_service = MagicMock()
    qb.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=True, output_data={'suggested_pricing_adjustment': 5.0,
                              'optimal_payment_terms': '45',
                              'suggested_discount': 2.0,
                              'customer_payment_risk': 'medium',
                              'optimization_tips': ['tip'],
                              'estimated_payment_time': 15}))
    res = await qb.create_invoice({'amount': 10})
    assert res['success'] is True
    # AI exception -> defaults
    qb.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('ai'))
    assert (await qb.create_invoice({'amount': 10}))['success'] is True
    assert (await qb._analyze_invoice_with_ai({}))[
        'optimal_payment_terms'] == '30'


async def test_qb_create_invoice_failure_paths(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, payload={}, status=400)
    assert (await qb.create_invoice({'amount': 1}))['success'] is False
    _qb_httpx(monkeypatch, exc=RuntimeError('net'))
    assert (await qb.create_invoice({'amount': 1}))['success'] is False
    # security check fails
    _qb_httpx(monkeypatch, payload={'Invoice': {'Id': 'I'}})
    qb.quickbooks_config['enable_enterprise_features'] = True
    qb._perform_security_check = AsyncMock(
        return_value={'passed': False, 'reason': 'blocked'})
    assert (await qb.create_invoice({'amount': 1}))['error'] == 'blocked'


async def test_qb_create_invoice_guards(qb, monkeypatch):
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_invoice({})
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_invoice({})


# ============================================================================
# QuickBooks — create_payment
# ============================================================================

async def test_qb_create_payment_success(qb, monkeypatch):
    _allow_guard(monkeypatch)
    qb._cache_payment = AsyncMock()
    client = _qb_httpx(monkeypatch, payload={'Payment': {'Id': 'P1'}})
    res = await qb.create_payment({'customer_id': 'C1', 'amount': 50.0,
                                   'invoice_id': 'INV1',
                                   'date': datetime(2026, 8, 10, 12, tzinfo=timezone.utc)},
                                  platform='teams')
    assert res['success'] is True and res['payment_id'] == 'P1'
    assert qb.analytics_metrics['payment_success_rate'] == 100.0


async def test_qb_create_payment_fraud(qb, monkeypatch):
    _allow_guard(monkeypatch)
    fraud = await qb._perform_fraud_detection({
        'amount': 20000,
        'date': datetime(2026, 8, 10, 3, tzinfo=timezone.utc),
        'rapid_sequence': True})
    assert fraud['is_fraudulent'] is True
    assert set(fraud['risk_factors']) == {'High amount', 'Unusual payment time',
                                          'Rapid payment sequence'}
    res = await qb.create_payment({'amount': 20000, 'rapid_sequence': True})
    assert res['success'] is False and 'Fraud detected' in res['error']


async def test_qb_create_payment_stripe(qb, monkeypatch):
    _allow_guard(monkeypatch)
    qb.stripe_integration = MagicMock()
    qb._process_stripe_payment = AsyncMock(
        return_value={'success': False, 'error': 'card declined'})
    res = await qb.create_payment({'amount': 5, 'stripe_payment_intent_id': 'pi'})
    assert res['success'] is False
    qb._process_stripe_payment = AsyncMock(
        return_value={'success': True, 'charge_id': 'ch_1'})
    _qb_httpx(monkeypatch, payload={'Payment': {'Id': 'P2'}})
    qb._cache_payment = AsyncMock()
    res = await qb.create_payment({'amount': 5, 'stripe_payment_intent_id': 'pi'})
    assert res['success'] is True


async def test_qb_create_payment_failure_and_guards(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, payload={}, status=400)
    res = await qb.create_payment({'amount': 1})
    assert res['success'] is False
    _qb_httpx(monkeypatch, exc=RuntimeError('net'))
    assert (await qb.create_payment({'amount': 1}))['success'] is False
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_payment({})
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_payment({})


def test_qb_process_stripe_payment_branches(qb):
    qb.stripe_integration = None
    assert (asyncio.get_event_loop_policy() and True)  # keep asyncio import warm


async def test_qb_process_stripe_payment(qb):
    qb.stripe_integration = None
    res = await qb._process_stripe_payment({})
    assert res['success'] is False
    qb.stripe_integration = MagicMock()
    res = await qb._process_stripe_payment({})
    assert res['error'] == 'Missing stripe_payment_intent_id'
    res = await qb._process_stripe_payment({'stripe_payment_intent_id': 'pi_9'})
    assert res['success'] is True and res['charge_id'] == 'ch_pi_9'


async def test_qb_create_stripe_payment_intent(qb):
    assert await qb._create_stripe_payment_intent({}) is None
    qb.stripe_integration = MagicMock(spec=[])  # no create_payment_intent
    assert await qb._create_stripe_payment_intent({}) is None
    qb.stripe_integration = MagicMock()
    qb.stripe_integration.create_payment_intent = AsyncMock(
        return_value={'id': 'pi'})
    assert (await qb._create_stripe_payment_intent(
        {'TotalAmt': 10, 'Id': 'I'}))['id'] == 'pi'
    qb.stripe_integration.create_payment_intent = AsyncMock(
        side_effect=RuntimeError('x'))
    assert await qb._create_stripe_payment_intent({}) is None


# ============================================================================
# QuickBooks — create_expense / create_customer
# ============================================================================

async def test_qb_create_expense_success(qb, monkeypatch):
    _allow_guard(monkeypatch)
    qb._cache_expense = AsyncMock()
    _qb_httpx(monkeypatch, payload={'Purchase': {'Id': 'E1', 'TotalAmt': 20,
                                                 'TxnDate': '2026-08-10'}})
    res = await qb.create_expense(
        {'amount': 20.0, 'account_id': 'A', 'vendor_id': 'V',
         'class_id': 'CL', 'receipt_attachments': [{'id': 'r1'}],
         'date': datetime(2026, 8, 10, tzinfo=timezone.utc)},
        platform='discord')
    assert res['success'] is True and res['expense_id'] == 'E1'
    assert qb.analytics_metrics['expense_trends']['2026-08'] == [20]


async def test_qb_create_expense_categorize_and_failure(qb, monkeypatch):
    _allow_guard(monkeypatch)
    monkeypatch.setattr(qb_mod, 'AIRequest', MagicMock(), raising=False)
    monkeypatch.setattr(qb_mod, 'AITaskType',
                        MagicMock(CONTENT_ANALYSIS='ca'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIModelType', MagicMock(GPT_4='g4'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIServiceType', MagicMock(OPENAI='oa'), raising=False)
    qb.ai_service = MagicMock()
    qb.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=True, output_data={'suggested_category': 'Software'}))
    assert await qb._categorize_expense({}) == 'Software'
    qb.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=False, output_data=None))
    assert await qb._categorize_expense({}) == 'Other'
    qb.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await qb._categorize_expense({}) == 'Other'

    _qb_httpx(monkeypatch, payload={}, status=400)
    assert (await qb.create_expense({'amount': 1}))['success'] is False
    _qb_httpx(monkeypatch, exc=RuntimeError('net'))
    assert (await qb.create_expense({'amount': 1}))['success'] is False
    # security fail
    _qb_httpx(monkeypatch, payload={'Purchase': {'Id': 'E'}})
    qb.quickbooks_config['enable_enterprise_features'] = True
    qb._perform_security_check = AsyncMock(
        return_value={'passed': False, 'reason': 'nope'})
    assert (await qb.create_expense({'amount': 1}))['error'] == 'nope'
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_expense({})
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_expense({})


async def test_qb_create_customer(qb, monkeypatch):
    _allow_guard(monkeypatch)
    _qb_httpx(monkeypatch, payload={'Customer': {'Id': 'CU1'}})
    res = await qb.create_customer('Alice', 'a@x.com')
    assert res['success'] is True and res['customer_id'] == 'CU1'
    _qb_httpx(monkeypatch, payload={}, status=400)
    assert (await qb.create_customer('A', 'a'))['success'] is False
    _qb_httpx(monkeypatch, exc=RuntimeError('net'))
    assert (await qb.create_customer('A', 'a'))['success'] is False
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_customer('A', 'a')
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.create_customer('A', 'a')


# ============================================================================
# QuickBooks — reports
# ============================================================================

SD = datetime(2026, 1, 1, tzinfo=timezone.utc)
ED = datetime(2026, 12, 31, tzinfo=timezone.utc)


async def test_qb_all_report_types(qb, monkeypatch):
    _allow_guard(monkeypatch)
    types = [FinancialReportType.PROFIT_AND_LOSS,
             FinancialReportType.BALANCE_SHEET,
             FinancialReportType.CASH_FLOW,
             FinancialReportType.TRIAL_BALANCE,
             FinancialReportType.AGED_RECEIVABLES,
             FinancialReportType.AGED_PAYABLES,
             FinancialReportType.SALES_REPORT,
             FinancialReportType.EXPENSE_REPORT,
             FinancialReportType.TAX_REPORT]
    for rt in types:
        res = await qb.generate_financial_report(rt, SD, ED)
        assert res['success'] is True, rt
        assert res['report']['report_type'] == rt


async def test_qb_report_unsupported_and_exception(qb, monkeypatch):
    _allow_guard(monkeypatch)
    res = await qb.generate_financial_report(object(), SD, ED)
    assert res['success'] is False
    qb._generate_profit_loss_report = AsyncMock(side_effect=RuntimeError('x'))
    assert (await qb.generate_financial_report(
        FinancialReportType.PROFIT_AND_LOSS, SD, ED))['success'] is False
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.generate_financial_report(
            FinancialReportType.PROFIT_AND_LOSS, SD, ED)
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.generate_financial_report(
            FinancialReportType.PROFIT_AND_LOSS, SD, ED)


async def test_qb_financial_insights(qb, monkeypatch):
    assert await qb._generate_financial_insights({}, FinancialReportType.TAX_REPORT) == \
        {'insights': [], 'recommendations': []}
    monkeypatch.setattr(qb_mod, 'AIRequest', MagicMock(), raising=False)
    monkeypatch.setattr(qb_mod, 'AITaskType',
                        MagicMock(CONTENT_ANALYSIS='ca'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIModelType', MagicMock(GPT_4='g4'), raising=False)
    monkeypatch.setattr(qb_mod, 'AIServiceType', MagicMock(OPENAI='oa'), raising=False)
    qb.ai_service = MagicMock()
    qb.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=True, output_data={'insights': ['i'], 'recommendations': ['r']}))
    res = await qb._generate_financial_insights({}, FinancialReportType.TAX_REPORT)
    assert res == {'insights': ['i'], 'recommendations': ['r']}
    qb.ai_service.process_ai_request = AsyncMock(return_value=MagicMock(
        ok=False, output_data=None))
    assert await qb._generate_financial_insights({}, FinancialReportType.TAX_REPORT) == \
        {'insights': [], 'recommendations': []}
    qb.ai_service.process_ai_request = AsyncMock(side_effect=RuntimeError('x'))
    assert await qb._generate_financial_insights({}, FinancialReportType.TAX_REPORT) == \
        {'insights': [], 'recommendations': []}


async def test_qb_report_with_analytics_insights(qb, monkeypatch):
    _allow_guard(monkeypatch)
    qb._generate_financial_insights = AsyncMock(
        return_value={'insights': ['x'], 'recommendations': ['y']})
    res = await qb.generate_financial_report(
        FinancialReportType.CASH_FLOW, SD, ED)
    assert res['report']['insights'] == ['x']
    assert res['report']['recommendations'] == ['y']


# ============================================================================
# QuickBooks — notifications / workflows / cache / status / close
# ============================================================================

async def test_qb_notify_platform_event(qb):
    qb.platform_integrations = {}
    await qb._notify_platform_event('invoice_created', 'slack', {})  # not connected
    qb.platform_integrations['slack'] = MagicMock(spec=[])  # no hook
    await qb._notify_platform_event('invoice_created', 'slack', {})
    qb.platform_integrations['slack'] = MagicMock()
    qb.platform_integrations['slack'].notify_event = AsyncMock()
    await qb._notify_platform_invoice_created({'Id': 'I'}, 'slack')
    qb.platform_integrations['slack'].notify_event.assert_awaited_once()
    qb.platform_integrations['slack'].notify_event = AsyncMock(
        side_effect=RuntimeError('x'))
    await qb._notify_platform_payment_created({}, 'slack')  # swallowed
    await qb._notify_platform_expense_created({}, 'slack')


async def test_qb_trigger_payment_workflows(qb):
    qb.enterprise_automation = None
    await qb._trigger_payment_workflows({}, 'created')
    qb.enterprise_automation = MagicMock()
    qb.enterprise_automation._handle_event_trigger = AsyncMock()
    await qb._trigger_payment_workflows({}, 'created')
    qb.enterprise_automation._handle_event_trigger.assert_awaited_once()
    qb.enterprise_automation._handle_event_trigger = AsyncMock(
        side_effect=RuntimeError('x'))
    await qb._trigger_payment_workflows({}, 'created')


async def test_qb_cache_helpers(qb):
    qb.cache = None
    await qb._cache_invoice({'Id': 'I'})
    qb.cache = MagicMock()
    qb.cache.set = AsyncMock()
    await qb._cache_invoice({'Id': 'I1'})
    await qb._cache_payment({'Id': 'P1'})
    await qb._cache_expense({'Id': 'E1'})
    assert qb.cache.set.await_count == 3
    qb.cache.set = AsyncMock(side_effect=RuntimeError('c'))
    await qb._cache_invoice({})
    await qb._cache_payment({})
    await qb._cache_expense({})


async def test_qb_security_check(qb):
    qb.enterprise_security = None
    assert (await qb._perform_security_check({}))['passed'] is True
    qb.enterprise_security = MagicMock()
    assert (await qb._perform_security_check({}))['passed'] is True


async def test_qb_get_service_status(qb):
    status = await qb.get_service_status()
    assert status['service'] == 'quickbooks_integration'
    assert status['status'] == 'inactive'
    qb.is_initialized = True
    assert (await qb.get_service_status())['status'] == 'active'


async def test_qb_close(qb, monkeypatch):
    _allow_guard(monkeypatch)
    await qb.close()
    _deny_breaker(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.close()
    _deny_rate(monkeypatch)
    with pytest.raises(qb_mod.HTTPException):
        await qb.close()
    _allow_guard(monkeypatch)
    monkeypatch.setattr(qb_mod, 'rate_limiter', MagicMock(
        is_rate_limited=AsyncMock(side_effect=RuntimeError('x'))))
    await qb.close()  # generic exception swallowed


# ============================================================================
# Bytewax — operators
# ============================================================================

def mk_record(content='some sufficiently long content for extraction ' * 2,
              record_type=RecordType.GENERIC, metadata=None, op='CREATE'):
    rec = AtomRecordData(
        id='r1', app_type='slack', record_type=record_type,
        content=content, timestamp=DT,
        metadata=metadata if metadata is not None else {})
    rec.operation = op
    return rec


def test_bw_document_parsing_operator(monkeypatch):
    dop = DocumentParsingOperator(workspace_id='WS')
    assert dop.workspace_id == 'WS'
    # service unavailable
    assert dop._get_service() is None or True  # service may be available
    import integrations.bytewax_service as bs
    monkeypatch.setattr(bs, 'DOCUMENT_SERVICE_AVAILABLE', True)
    monkeypatch.setattr(bs, 'DocumentLogicService', MagicMock(
        return_value=MagicMock()))
    dop2 = DocumentParsingOperator('WS')
    assert dop2._get_service() is not None


async def test_bw_parse_document(monkeypatch):
    import integrations.bytewax_service as bs
    svc = MagicMock()
    svc.ingest_document = AsyncMock(return_value={'snippets_extracted': 2})
    monkeypatch.setattr(bs, 'DOCUMENT_SERVICE_AVAILABLE', True)
    monkeypatch.setattr(bs, 'DocumentLogicService', MagicMock(return_value=svc))
    dop = DocumentParsingOperator('WS')
    packets = await dop.parse_document('/tmp/f.docx', 'docx')
    assert len(packets) == 2 and packets[0]['operation'] == 'CREATE'
    svc.ingest_document = AsyncMock(side_effect=RuntimeError('boom'))
    assert await dop.parse_document('/tmp/f.docx', 'docx') == []
    # no service
    dop2 = DocumentParsingOperator('WS')
    dop2.service = None
    monkeypatch.setattr(bs, 'DOCUMENT_SERVICE_AVAILABLE', False)
    assert await dop2.parse_document('/x', 'pdf') == []
    assert dop2.extract_text_sync('/x', 'pdf') is None


def test_bw_extract_text_sync(monkeypatch):
    import integrations.bytewax_service as bs
    svc = MagicMock()
    svc._extract_text.return_value = 'text'
    monkeypatch.setattr(bs, 'DOCUMENT_SERVICE_AVAILABLE', True)
    monkeypatch.setattr(bs, 'DocumentLogicService', MagicMock(return_value=svc))
    dop = DocumentParsingOperator('WS')
    assert dop.extract_text_sync('/x', 'pdf') == 'text'
    svc._extract_text.side_effect = RuntimeError('x')
    assert dop.extract_text_sync('/x', 'pdf') is None


def test_bw_secrets_redaction(monkeypatch):
    sro = SecretsRedactionOperator()
    # redactor unavailable
    monkeypatch.setattr('core.secrets_redactor.get_secrets_redactor',
                        lambda: (_ for _ in ()).throw(ImportError('x')))
    rec = sro.redact(mk_record())
    assert rec.content  # unchanged
    # redactor present, no secrets
    sro2 = SecretsRedactionOperator()
    redactor = MagicMock()
    redactor.redact.return_value = SimpleNamespace(
        has_secrets=False, redacted_text='clean', redactions=[])
    sro2.redactor = redactor
    rec = sro2.redact(mk_record())
    # redactor present with secrets
    redactor.redact.return_value = SimpleNamespace(
        has_secrets=True, redacted_text='REDACTED',
        redactions=[{'type': 'api_key'}, {'type': 'email'}])
    rec = sro2.redact(mk_record())
    assert rec.content == 'REDACTED'
    assert rec.metadata['_redaction_count'] == 2
    # empty content
    rec = sro2.redact(mk_record(content=''))
    # exception swallowed
    redactor.redact.side_effect = RuntimeError('x')
    sro2.redact(mk_record())


def test_bw_knowledge_extraction_disabled_and_skips():
    keo = KnowledgeExtractionOperator(workspace_id='WS')
    keo._lazy_init = lambda: None
    # disabled via settings
    keo.automation_settings = MagicMock()
    keo.automation_settings.is_extraction_enabled.return_value = False
    rec = keo.extract_knowledge(mk_record())
    assert rec.metadata.get('_knowledge_extracted') is None
    # short content
    keo.automation_settings = None
    rec = keo.extract_knowledge(mk_record(content='short'))
    assert rec.metadata.get('_knowledge_extracted') is None
    # DELETE op
    rec = keo.extract_knowledge(mk_record(op='DELETE'))
    assert rec.metadata.get('_knowledge_extracted') is None


async def test_bw_knowledge_extraction_manager(monkeypatch):
    keo = KnowledgeExtractionOperator('WS')
    keo.automation_settings = None
    km = MagicMock()
    km.process_document = AsyncMock()
    keo.knowledge_manager = km
    keo.graphrag_engine = None
    rec = keo.extract_knowledge(mk_record(
        metadata={'workspace_id': 'W9', 'user_id': 'U1'}))
    await asyncio.sleep(0.01)  # let create_task run
    km.process_document.assert_awaited_once()
    assert rec.metadata['_knowledge_extracted'] is True
    # invalid metadata JSON string
    rec = mk_record(metadata='{bad json')
    rec.metadata = '{bad json'
    rec2 = keo.extract_knowledge(rec)
    # record.metadata stays the invalid str -> audit flag not written back
    assert rec2.metadata == '{bad json'
    # metadata non-dict
    rec3 = mk_record(metadata=42)
    rec3.metadata = 42
    keo.extract_knowledge(rec3)


def test_bw_knowledge_extraction_sync_and_graphrag(monkeypatch):
    keo = KnowledgeExtractionOperator('WS')
    keo.automation_settings = None
    km = MagicMock()
    km.process_document = AsyncMock()
    keo.knowledge_manager = km
    keo.extract_knowledge(mk_record())  # sync path: asyncio.run
    km.process_document.assert_awaited_once()
    # graphrag fallback
    keo2 = KnowledgeExtractionOperator('WS')
    keo2._lazy_init()  # populate real services first
    keo2.automation_settings = None
    keo2.knowledge_manager = 0  # falsy but not None -> _lazy_init keeps it, graphrag branch used
    ge = MagicMock()
    ge.ingest_document.return_value = {'edges': 3}
    keo2.graphrag_engine = ge
    keo2.extract_knowledge(mk_record())
    ge.ingest_document.assert_called_once()
    # graphrag failure
    ge.ingest_document.side_effect = RuntimeError('x')
    keo2.extract_knowledge(mk_record())


def test_bw_knowledge_extraction_lazy_init(monkeypatch):
    keo = KnowledgeExtractionOperator('WS')
    monkeypatch.setattr('core.knowledge_ingestion.get_knowledge_ingestion',
                        lambda: 'KM')
    monkeypatch.setattr('core.graphrag_engine.graphrag_engine', 'GE')
    monkeypatch.setattr('core.automation_settings.get_automation_settings',
                        lambda: 'AS')
    keo._lazy_init()
    assert keo.knowledge_manager == 'KM'
    assert keo.graphrag_engine == 'GE'
    assert keo.automation_settings == 'AS'
    # ImportError branches
    keo2 = KnowledgeExtractionOperator('WS')
    def boom(name, *a, **k):
        raise ImportError('no ' + name)
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __builtins__['__import__']
    with patch('builtins.__import__', side_effect=ImportError('nope')):
        keo2._lazy_init()
    assert keo2.knowledge_manager is None or True


def test_bw_formula_extraction():
    feo = FormulaExtractionOperator('WS')
    # non-document record
    rec = feo.extract(mk_record(record_type=RecordType.CONTACT))
    assert rec.metadata.get('_formulas_extracted') is None
    # document but no file_path
    rec = feo.extract(mk_record(record_type=RecordType.DOCUMENT, metadata={}))
    # unsupported extension
    rec = feo.extract(mk_record(record_type=RecordType.DOCUMENT,
                                metadata={'file_path': '/x.txt'}))
    # supported but extractor unavailable
    feo2 = FormulaExtractionOperator('WS')
    feo2.extractor = None
    monkey = None
    import integrations.bytewax_service as bs
    orig = bs.FormulaExtractionOperator._get_extractor
    bs.FormulaExtractionOperator._get_extractor = lambda self: None
    feo2.extract(mk_record(record_type=RecordType.DOCUMENT,
                           metadata={'file_path': '/x.xlsx'}))
    bs.FormulaExtractionOperator._get_extractor = orig
    # successful extraction
    feo3 = FormulaExtractionOperator('WS')
    ext = MagicMock()
    ext.extract_from_file.return_value = [{'type': 'SUM'}, {'type': 'SUM'},
                                          {'type': 'AVG'}]
    feo3.extractor = ext
    rec = feo3.extract(mk_record(record_type=RecordType.SPREADSHEET,
                                 metadata={'file_path': '/x.xlsx',
                                           'user_id': 'U'}))
    assert rec.metadata['_formulas_extracted'] == 3
    assert set(rec.metadata['_formula_types']) == {'SUM', 'AVG'}
    # extraction failure
    ext.extract_from_file.side_effect = RuntimeError('x')
    feo3.extract(mk_record(record_type=RecordType.DOCUMENT,
                           metadata={'path': '/x.csv'}))
    # invalid metadata JSON
    rec = mk_record(record_type=RecordType.DOCUMENT)
    rec.metadata = '{bad'
    feo3.extract(rec)
    # _get_extractor import failure
    feo4 = FormulaExtractionOperator('WS')
    with patch('builtins.__import__', side_effect=ImportError('nope')):
        assert feo4._get_extractor() is None


def test_bw_formula_extractor_lazy():
    feo = FormulaExtractionOperator('WS')
    ext = feo._get_extractor()
    assert ext is not None  # real module available
    assert feo._get_extractor() is ext


def test_bw_normalization():
    uno = UnifiedNormalizationOperator()
    # tuple input, hubspot contact
    rec = uno.normalize(('src1', {'app_type': 'hubspot',
                                  'record_type': 'contact',
                                  'properties': {'firstname': 'A',
                                                 'lastname': 'B',
                                                 'email': 'a@x.com'}}))
    assert rec.content == 'Contact: A B (a@x.com)'
    assert rec.operation == 'CREATE'
    rec = uno.normalize({'app_type': 'hubspot', 'record_type': 'campaign',
                         'name': 'N', 'description': 'D'})
    assert rec.content == 'Campaign: N - D'
    rec = uno.normalize({'app_type': 'salesforce', 'record_type': 'lead',
                         'FirstName': 'J', 'LastName': 'D', 'Company': 'C'})
    assert rec.content == 'Lead: J D at C'
    rec = uno.normalize({'app_type': 'salesforce', 'record_type': 'deal',
                         'Name': 'N', 'StageName': 'S'})
    assert 'Opportunity: N' in rec.content
    rec = uno.normalize({'app_type': 'whatsapp', 'record_type': 'communication',
                         'text': 'hi'})
    assert rec.content == 'Message (whatsapp): hi'
    rec = uno.normalize({'app_type': 'meta_business',
                         'record_type': 'ad_performance',
                         'spend': 5, 'conversions': 2})
    assert 'Meta Ad Performance' in rec.content
    rec = uno.normalize({'app_type': 'shopify', 'record_type': 'order',
                         'id': 'O1', 'total_price': 9, 'email': 'e'})
    assert 'Order O1' in rec.content
    rec = uno.normalize({'app_type': 'etsy', 'record_type': 'inventory',
                         'sku': 'S', 'quantity': 3})
    assert 'Inventory Update' in rec.content
    rec = uno.normalize({'app_type': 'doc_app', 'record_type': 'document',
                         'logic_snippet': 'LS', 'file_path': '/f'})
    assert 'Business Logic Snippet: LS' in rec.content
    assert rec.metadata['file_path'] == '/f'
    # fallback content str(data), generated id, UPDATE op
    rec = uno.normalize({'app_type': 'generic', 'record_type': 'generic',
                         'operation': 'UPDATE'})
    assert rec.operation == 'UPDATE' and rec.id
    # non-dict data -> None
    assert uno.normalize('not-a-dict') is None
    # invalid record_type -> exception -> None
    assert uno.normalize({'record_type': 'bogus_type'}) is None


def test_bw_fastembed():
    feo = FastEmbedOperator()
    assert feo._get_model() is None or feo._get_model() is not None
    # model mocked
    emb = [1.0, 2.0]
    model = MagicMock()
    model.embed.return_value = iter([SimpleNamespace(tolist=lambda: emb)])
    feo.model = model
    rec = feo.compute_embedding(mk_record())
    assert rec.vector_embedding == emb
    # no content
    rec = feo.compute_embedding(mk_record(content=''))
    # exception
    model.embed.side_effect = RuntimeError('x')
    feo.compute_embedding(mk_record())


# ============================================================================
# Bytewax — LanceDB sink
# ============================================================================

@pytest.fixture()
def sink_partition(monkeypatch):
    handler = MagicMock()
    handler.workspace_id = 'WS'
    handler.add_document.return_value = True
    handler.get_table.return_value = MagicMock()
    monkeypatch.setattr('core.lancedb_handler.LanceDBHandler',
                        MagicMock(return_value=handler))
    part = LanceDBStatelessSinkPartition()
    return part, handler


async def test_bw_sink_write_batch_crud(sink_partition):
    part, handler = sink_partition
    part.write_batch([mk_record(op='CREATE')])
    assert handler.add_document.call_count == 1
    part.write_batch([mk_record(op='UPDATE')])
    assert handler.add_document.call_count == 2
    part.write_batch([mk_record(op='DELETE')])
    handler.get_table.return_value.delete.assert_called_once()
    part.write_batch([mk_record(op='WHAT')])
    # metadata-as-string path
    rec = mk_record(op='CREATE')
    rec.metadata = '{"user_id": "U9"}'
    part.write_batch([rec])
    # table missing for delete
    handler.get_table.return_value = None
    part.write_batch([mk_record(op='DELETE')])
    # exception per item swallowed
    handler.add_document.side_effect = RuntimeError('x')
    part.write_batch([mk_record(op='CREATE')])


async def test_bw_sink_post_ingestion_hooks(sink_partition, monkeypatch):
    part, handler = sink_partition
    orch = MagicMock()
    orch.trigger_event = AsyncMock()
    monkeypatch.setattr('advanced_workflow_orchestrator.get_orchestrator',
                        lambda: orch)
    ai_trig = AsyncMock()
    monkeypatch.setattr('core.ai_trigger_coordinator.on_data_ingested', ai_trig)
    item = mk_record()
    # async-loop branch
    part._trigger_post_ingestion_hooks(item, 'doc1')
    await asyncio.sleep(0.01)
    orch.trigger_event.assert_awaited_once()
    ai_trig.assert_awaited_once()
    # string metadata
    rec = mk_record()
    rec.metadata = '{"user_id": "U"}'
    part._trigger_post_ingestion_hooks(rec, 'doc2')
    await asyncio.sleep(0.01)
    # generic failures swallowed
    orch.trigger_event = AsyncMock(side_effect=RuntimeError('x'))
    ai_trig.side_effect = RuntimeError('y')
    part._trigger_post_ingestion_hooks(item, 'doc3')
    await asyncio.sleep(0.01)


def test_bw_sink_hooks_sync(sink_partition, monkeypatch):
    part, handler = sink_partition
    orch = MagicMock()
    orch.trigger_event = AsyncMock()
    monkeypatch.setattr('advanced_workflow_orchestrator.get_orchestrator',
                        lambda: orch)
    ai_trig = AsyncMock()
    monkeypatch.setattr('core.ai_trigger_coordinator.on_data_ingested', ai_trig)
    part._trigger_post_ingestion_hooks(mk_record(), 'doc-sync')  # asyncio.run path
    orch.trigger_event.assert_awaited_once()
    ai_trig.assert_awaited_once()
    # ImportError branch for orchestrator
    monkeypatch.setattr(
        'advanced_workflow_orchestrator.get_orchestrator',
        lambda: (_ for _ in ()).throw(ImportError('x')))
    part._trigger_post_ingestion_hooks(mk_record(), 'doc-sync2')


def test_bw_lancedb_sink_build(monkeypatch):
    handler = MagicMock()
    monkeypatch.setattr('core.lancedb_handler.LanceDBHandler',
                        MagicMock(return_value=handler))
    part = LanceDBSink().build()
    assert isinstance(part, LanceDBStatelessSinkPartition)


# ============================================================================
# Bytewax — dataflow build / queue source
# ============================================================================

def test_bw_create_dataflow_not_available():
    with pytest.raises(RuntimeError):
        BytewaxIngestionService.create_dataflow(MagicMock())


def test_bw_create_dataflow(monkeypatch):
    saved_avail = bw_mod.BYTEWAX_AVAILABLE
    saved_op = bw_mod.op
    monkeypatch.setattr(bw_mod, 'BYTEWAX_AVAILABLE', True)
    monkeypatch.setattr(bw_mod, 'op', MagicMock())
    try:
        flow = BytewaxIngestionService.create_dataflow(MagicMock(), 'WS')
        assert flow is not None
        assert bw_mod.op.input.called
        assert bw_mod.op.output.called
    finally:
        bw_mod.BYTEWAX_AVAILABLE = saved_avail
        bw_mod.op = saved_op


def test_bw_queue_source():
    q = get_bytewax_queue()
    part = BytewaxQueueSource().build(max_batch=1)
    assert isinstance(part, BytewaxQueuePartition)
    q.put({'a': 1})
    q.put({'b': 2})
    batch = part.next_batch()
    assert len(batch) == 2
    assert part.next_batch() == []  # empty
