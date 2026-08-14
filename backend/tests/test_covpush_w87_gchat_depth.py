# -*- coding: utf-8 -*-
"""Coverage wave 87 — integrations.google_chat_analytics_engine,
integrations.google_chat_enhanced_service.

No network, no LLM: all Google API boundaries (build, Flow) and HTTP calls are
mocked; Session/DB objects are plain fakes.
"""
import json
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cryptography.fernet import Fernet

import integrations.google_chat_analytics_engine as an_mod
import integrations.google_chat_enhanced_service as svc_mod
from integrations.google_chat_analytics_engine import (
    GoogleChatAnalyticsEngine,
    GoogleChatAnalyticsMetric as Metric,
    GoogleChatAnalyticsTimeRange as TR,
    GoogleChatAnalyticsGranularity as Gran,
    GoogleChatAnalyticsDataPoint,
)
from integrations.google_chat_enhanced_service import (
    GoogleChatEnhancedService,
    GoogleChatRateLimiter,
    GoogleChatSpace,
    GoogleChatConnectionStatus,
)

DT = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


# ============================================================================
# Analytics engine — fakes / fixtures
# ============================================================================

class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """Fake DB whose execute() pops the next row-list per call (or reuses
    `rows` for every call when `queues` is not given)."""
    def __init__(self, rows=None, queues=None):
        self.rows = rows or []
        self.queues = list(queues) if queues else None
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        if self.queues is not None:
            rows = self.queues.pop(0) if self.queues else []
        else:
            rows = self.rows
        return FakeCursor(rows)


def mk_point(ts=DT, metric=Metric.MESSAGE_COUNT, value=10):
    return GoogleChatAnalyticsDataPoint(
        timestamp=ts, metric=metric, value=value,
        dimensions={'a': 1}, metadata={'b': 2})


@pytest.fixture()
def engine():
    return GoogleChatAnalyticsEngine({'database': None, 'redis': {'client': None}})


@pytest.fixture()
def redis():
    r = MagicMock()
    r.get.return_value = None
    r.setex = MagicMock()
    r.keys.return_value = []
    return r


# ============================================================================
# Analytics — get_analytics, cache, mock data
# ============================================================================

async def test_an_get_analytics_mock_data_no_db(engine):
    pts = await engine.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_24_HOURS,
                                     Gran.HOUR)
    assert len(pts) == 25  # 24 hours inclusive
    assert pts[0].metadata['data_source'] == 'mock_generator'
    assert pts[0].value >= 0


async def test_an_get_analytics_sentiment_topics_mock_no_db(engine):
    # no db -> _fetch_raw_messages returns [] -> empty data points
    assert await engine.get_analytics(Metric.SENTIMENT, TR.LAST_7_DAYS, Gran.DAY) == []
    assert await engine.get_analytics(Metric.TOPICS, TR.LAST_7_DAYS, Gran.DAY) == []


async def test_an_get_analytics_db_path(engine):
    engine.db = FakeDB(rows=[{'timestamp': DT, 'value': 42}])
    pts = await engine.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert len(pts) == 1 and pts[0].value == 42


async def test_an_get_analytics_cache_hit_and_store(redis):
    eng = GoogleChatAnalyticsEngine({'database': None, 'redis': {'client': redis}})
    eng._get_time_range_boundaries = lambda tr: (DT, DT)
    cached = [mk_point().to_dict()]
    redis.get.return_value = json.dumps(cached)
    pts = await eng.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert pts[0].value == 10
    redis.setex.assert_not_called()  # hit -> no re-store


async def test_an_cache_store_and_error(redis):
    eng = GoogleChatAnalyticsEngine({'database': None, 'redis': {'client': redis}})
    eng._get_time_range_boundaries = lambda tr: (DT, DT)
    await eng.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert redis.setex.called
    # corrupt cache payload -> miss -> regenerated
    redis.get.return_value = '{not json'
    pts = await eng.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert pts
    # cache-result error swallowed
    redis.setex.side_effect = RuntimeError('redis down')
    assert await eng.get_analytics(Metric.ACTIVE_USERS, TR.LAST_7_DAYS, Gran.DAY)


async def test_an_get_analytics_outer_exception(engine):
    engine._get_time_range_boundaries = MagicMock(side_effect=RuntimeError('boom'))
    assert await engine.get_analytics(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY) == []


async def test_an_fetch_exception_returns_empty(engine):
    engine.db = MagicMock()
    engine.db.execute.side_effect = RuntimeError('db')
    assert await engine._fetch_analytics_data(
        Metric.MESSAGE_COUNT, DT, DT, Gran.DAY) == []


# ============================================================================
# Analytics — query builder branches
# ============================================================================

@pytest.mark.parametrize('metric,expected_frag', [
    (Metric.MESSAGE_COUNT, 'COUNT(*)'),
    (Metric.ACTIVE_USERS, 'COUNT(DISTINCT user_id)'),
    (Metric.BOT_MESSAGE_COUNT, "sender_type = 'BOT'"),
    (Metric.HUMAN_MESSAGE_COUNT, "sender_type = 'HUMAN'"),
    (Metric.THREAD_CREATION, 'thread_id IS NOT NULL'),
    (Metric.CARD_INTERACTIONS, 'json_extract'),
    (Metric.RESPONSE_TIME, 'AVG(response_time)'),
    (Metric.REACTION_COUNT, 'json_array_length'),
    (Metric.MESSAGE_FREQUENCY, 'COUNT(*)'),  # default branch
    (Metric.SPACE_ACTIVITY, 'COUNT(*)'),
    (Metric.USER_ENGAGEMENT, 'COUNT(*)'),
])
async def test_an_build_query_metric_branches(engine, metric, expected_frag):
    q = await engine._build_analytics_query(
        metric, DT, DT, Gran.DAY, workspace_id='ws1',
        space_ids=['s1', 's2'], user_ids=['u1'])
    assert expected_frag in q['sql']
    assert '{dimensions}' not in q['sql']


async def test_an_build_query_filters(engine):
    q = await engine._build_analytics_query(
        Metric.MESSAGE_COUNT, DT, DT, Gran.WEEK,
        filters={'sender_type': 'HUMAN', 'tag': ['a', 'b']})
    assert 'sender_type = ?' in q['sql'] and 'tag IN (?,?)' in q['sql']


async def test_an_build_query_unsupported_metric(engine):
    q = await engine._build_analytics_query(
        Metric.SENTIMENT, DT, DT, Gran.DAY)
    assert q == {'sql': '', 'params': []}


# ============================================================================
# Analytics — mock generation helpers
# ============================================================================

def test_an_interval_delta_and_mock_value(engine):
    assert engine._get_interval_delta(Gran.HOUR) == timedelta(hours=1)
    assert engine._get_interval_delta(Gran.WEEK) == timedelta(weeks=1)
    assert engine._get_interval_delta(Gran.MONTH) == timedelta(days=30)
    assert engine._get_interval_delta(Gran.YEAR) == timedelta(days=1)  # fallback
    v1 = engine._generate_mock_value(Metric.MESSAGE_COUNT, DT)
    v2 = engine._generate_mock_value(Metric.REACTION_COUNT, DT.replace(hour=3))
    assert v1 >= 0 and v2 >= 0
    assert engine._generate_mock_value(Metric.SENTIMENT, DT) >= 0  # default base 50


async def test_an_generate_mock_data_exception(engine, monkeypatch):
    monkeypatch.setattr(engine, '_get_interval_delta',
                        MagicMock(side_effect=RuntimeError('x')))
    assert await engine._generate_mock_analytics_data(
        Metric.MESSAGE_COUNT, DT, DT, Gran.DAY) == []


def test_an_time_range_boundaries(engine):
    for tr in (TR.LAST_24_HOURS, TR.LAST_7_DAYS, TR.LAST_30_DAYS, TR.LAST_90_DAYS,
               TR.CUSTOM):
        start, end = engine._get_time_range_boundaries(tr)
        assert start < end


def test_an_cache_key_generation(engine):
    key = engine._generate_cache_key(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY,
        filters={'x': 1}, workspace_id='w', space_ids=['b', 'a'], user_ids=['u'])
    assert key.startswith('google_chat_analytics')
    assert 'spaces:a,b' in key


# ============================================================================
# Analytics — top spaces / user summary / space report
# ============================================================================

async def test_an_top_spaces_mock(engine):
    res = await engine.get_top_spaces(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, limit=3)
    assert len(res) == 3 and res[0]['metric'] == 'message_count'


async def test_an_top_spaces_db(engine):
    engine.db = FakeDB(rows=[{'space_id': 's1', 'space_name': 'S1',
                              'value': 5, 'human_ratio': 0.9}])
    res = await engine.get_top_spaces(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS,
                                      workspace_id='w')
    assert res[0]['space_id'] == 's1'
    # unsupported metric -> []
    res2 = await engine.get_top_spaces(Metric.SENTIMENT, TR.LAST_7_DAYS)
    assert res2 == []


async def test_an_top_spaces_exception(engine):
    engine._get_time_range_boundaries = MagicMock(side_effect=RuntimeError('x'))
    assert await engine.get_top_spaces(Metric.MESSAGE_COUNT, TR.LAST_7_DAYS) == []


async def test_an_user_activity_summary_mock(engine):
    res = await engine.get_user_activity_summary('u1', TR.LAST_30_DAYS)
    assert res['message_count'] == 150 and res['engagement_score'] == 0.78


async def test_an_user_activity_summary_db(engine):
    engine.db = FakeDB(queues=[
        [{'message_count': 100, 'spaces_participated': 3, 'threads_created': 4,
          'reactions_given': 10, 'card_interactions': 2, 'avg_message_length': 50}],
        [{'hour': '10'}, {'hour': '14'}],
    ])
    res = await engine.get_user_activity_summary('u1', TR.LAST_7_DAYS)
    assert res['message_count'] == 100 and res['most_active_hours'] == [10, 14]
    assert res['engagement_score'] == 0.5


async def test_an_user_activity_summary_exception(engine):
    engine.db = MagicMock()
    engine.db.execute.side_effect = RuntimeError('db')
    res = await engine.get_user_activity_summary('u1', TR.LAST_7_DAYS)
    assert res['success'] is False and res['operation'] == 'get_user_activity_summary'


async def test_an_space_activity_report_mock(engine):
    res = await engine.get_space_activity_report('s1', TR.LAST_7_DAYS)
    assert res['total_messages'] == 1250 and res['engagement_trend'] == 'increasing'


async def test_an_space_activity_report_db(engine):
    engine.db = FakeDB(queues=[
        [{'total_messages': 10, 'active_users': 2, 'new_threads': 3,
          'card_interactions': 1, 'bot_messages': 4, 'human_messages': 6,
          'avg_message_length': 20, 'hour': '09'}],
        [{'hour': '09'}],
        [{'user_name': 'Alice', 'message_count': 7}],
    ])
    res = await engine.get_space_activity_report('s1', TR.LAST_7_DAYS)
    assert res['total_messages'] == 10 and res['peak_activity_hour'] == 9
    assert res['top_contributors'][0]['user_name'] == 'Alice'


async def test_an_space_activity_report_exception(engine):
    engine.db = MagicMock()
    engine.db.execute.side_effect = RuntimeError('db')
    res = await engine.get_space_activity_report('s1', TR.LAST_7_DAYS)
    assert res['success'] is False


# ============================================================================
# Analytics — export
# ============================================================================

async def test_an_export_csv_json(engine, monkeypatch):
    monkeypatch.setattr(engine, 'get_analytics',
                        AsyncMock(return_value=[mk_point(value=7)]))
    csv_res = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='csv')
    assert csv_res['ok'] and 'timestamp' in csv_res['data']
    json_res = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='JSON')
    assert json_res['ok'] and json_res['format'] == 'json'


async def test_an_export_no_data_unsupported_error(engine, monkeypatch):
    monkeypatch.setattr(engine, 'get_analytics', AsyncMock(return_value=[]))
    res = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert res['ok'] is False
    monkeypatch.setattr(engine, 'get_analytics', AsyncMock(return_value=[mk_point()]))
    res2 = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='pdf')
    assert 'Unsupported format' in res2['error']
    monkeypatch.setattr(engine, 'get_analytics',
                        AsyncMock(side_effect=RuntimeError('x')))
    res3 = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY)
    assert res3['ok'] is False


async def test_an_export_excel(engine, monkeypatch):
    pts = [mk_point(value=5, ts=DT), mk_point(value=9, ts=DT + timedelta(days=1))]
    monkeypatch.setattr(engine, 'get_analytics', AsyncMock(return_value=pts))
    if not an_mod.OPENPYXL_AVAILABLE:
        res = await engine.export_analytics_data(
            Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='excel')
        assert res['ok'] is False and 'openpyxl' in res['error']
        return
    res = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='excel')
    assert res['ok'] and res['filename'].endswith('.xlsx')
    # converter failure -> not ok
    monkeypatch.setattr(engine, '_convert_to_excel',
                        MagicMock(return_value=None))
    res2 = await engine.export_analytics_data(
        Metric.MESSAGE_COUNT, TR.LAST_7_DAYS, Gran.DAY, format='excel')
    assert res2['ok'] is False


def test_an_convert_to_csv_branches(engine):
    assert engine._convert_to_csv([]) == ''
    out = engine._convert_to_csv([mk_point(value='a"b')])
    assert '""' in out  # quote escaping


def test_an_convert_to_excel_none_and_error(engine):
    assert engine._convert_to_excel([], Metric.MESSAGE_COUNT, TR.LAST_7_DAYS) is None
    if an_mod.OPENPYXL_AVAILABLE:
        with patch.object(an_mod, 'Workbook', side_effect=RuntimeError('x')):
            assert engine._convert_to_excel(
                [mk_point()], Metric.MESSAGE_COUNT, TR.LAST_7_DAYS) is None


async def test_an_clear_cache(engine, redis):
    eng = GoogleChatAnalyticsEngine({'database': None, 'redis': {'client': redis}})
    redis.keys.return_value = ['google_chat_analytics|a', 'google_chat_analytics|b']
    await eng.clear_cache()
    redis.delete.assert_called_once()
    # no keys / no redis / error paths
    redis.keys.return_value = []
    await eng.clear_cache()
    await engine.clear_cache()  # no redis client
    redis.keys.side_effect = RuntimeError('x')
    await eng.clear_cache()


# ============================================================================
# Analytics — AI sentiment / topics
# ============================================================================

def _mk_raw_messages():
    return [
        {'timestamp': DT.replace(minute=0, second=0, microsecond=0), 'content': 'great stuff here'},
        {'timestamp': DT.isoformat(), 'content': 'more text'},
    ]


async def test_an_sentiment_analytics(engine, monkeypatch):
    engine.db = FakeDB(rows=_mk_raw_messages())
    monkeypatch.setattr(an_mod, 'get_llm_service', MagicMock(
        return_value=SimpleNamespace(generate_structured=AsyncMock(
            return_value=an_mod.LLMSentiment(score=0.8, label='positive',
                                             confidence=0.9)))))
    pts = await engine.get_analytics(Metric.SENTIMENT, TR.LAST_7_DAYS, Gran.DAY)
    assert pts and pts[0].value == 0.8 and pts[0].dimensions['label'] == 'positive'


async def test_an_topics_analytics(engine, monkeypatch):
    engine.db = FakeDB(rows=_mk_raw_messages())
    monkeypatch.setattr(an_mod, 'get_llm_service', MagicMock(
        return_value=SimpleNamespace(generate_structured=AsyncMock(
            return_value=an_mod.LLMTopics(topics=['deploys', 'incidents'],
                                          confidence=0.7)))))
    pts = await engine.get_analytics(Metric.TOPICS, TR.LAST_7_DAYS, Gran.DAY)
    assert pts and 'deploys' in pts[0].value


async def test_an_sentiment_topics_llm_failure(engine, monkeypatch):
    engine.db = FakeDB(rows=_mk_raw_messages())
    monkeypatch.setattr(an_mod, 'get_llm_service',
                        MagicMock(side_effect=RuntimeError('llm down')))
    pts = await engine.get_analytics(Metric.SENTIMENT, TR.LAST_7_DAYS, Gran.DAY)
    assert pts[0].value == 0.0 and pts[0].metadata['confidence'] == 0.0
    pts2 = await engine.get_analytics(Metric.TOPICS, TR.LAST_7_DAYS, Gran.DAY)
    assert pts2[0].value == ''


async def test_an_analyze_sentiment_short_text(engine):
    assert await engine._analyze_sentiment('ab') == {
        'score': 0.0, 'label': 'neutral', 'confidence': 1.0}
    assert await engine._extract_topics([]) == {'topics': [], 'confidence': 1.0}


def test_an_group_messages(engine):
    grouped = engine._group_messages_by_granularity(_mk_raw_messages(), Gran.HOUR)
    assert len(grouped) == 1
    grouped_day = engine._group_messages_by_granularity(
        _mk_raw_messages(), Gran.DAY)
    assert len(grouped_day) == 1
    grouped_week = engine._group_messages_by_granularity(
        _mk_raw_messages(), Gran.WEEK)
    assert grouped_week  # else branch keeps raw ts


async def test_an_fetch_raw_messages_error(engine):
    engine.db = MagicMock()
    engine.db.execute.side_effect = RuntimeError('db')
    assert await engine._fetch_raw_messages(DT, DT) == []


def test_an_engine_info_and_singleton():
    info = an_mod.google_chat_analytics_engine.get_engine_info()
    assert info['status'] == 'ACTIVE' and info['version'] == '3.0.0'
    eng = GoogleChatAnalyticsEngine({'database': None, 'redis': {'client': None}})
    info2 = eng.get_engine_info()
    assert len(info2['supported_metrics']) == 13


# ============================================================================
# Enhanced service — fixtures
# ============================================================================

FERNET_KEY = Fernet.generate_key().decode()


def make_service(db=None, redis_client=None, creds=True):
    cfg = {
        'database': db,
        'redis': {'client': redis_client},
        'encryption_key': FERNET_KEY,
    }
    if creds:
        cfg.update({'client_id': 'cid', 'client_secret': 'csec',
                    'redirect_uri': 'https://cb'})
    svc = GoogleChatEnhancedService(tenant_id='t1', config=cfg)
    return svc


SPACE_ROW = {
    'space_id': 'spaces/S1', 'name': 'spaces/S1', 'display_name': 'Space One',
    'type': 'ROOM', 'user_id': 'u1',
    'access_token': Fernet(FERNET_KEY.encode()).encrypt(b'tok').decode(),
    'refresh_token': 'rt',
}


@pytest.fixture()
def svc():
    s = make_service()
    s._get_user_space_by_id = MagicMock(return_value=GoogleChatSpace(**SPACE_ROW))
    return s


def chat_service_mock(spaces_get=None, messages_create=None, messages_list=None):
    cs = MagicMock()
    if spaces_get is not None:
        cs.spaces().get().execute.return_value = spaces_get
    if messages_create is not None:
        cs.spaces().messages().create().execute.return_value = messages_create
    if messages_list is not None:
        cs.spaces().messages().list().execute.return_value = messages_list
    return cs


# ============================================================================
# Enhanced service — init / oauth flow
# ============================================================================

def test_svc_init_without_creds(monkeypatch):
    monkeypatch.setattr(svc_mod, 'Flow', MagicMock(
        from_client_config=MagicMock(side_effect=RuntimeError('bad config'))))
    svc = make_service()
    assert svc.oauth_flow is None  # error path swallowed


def test_svc_token_encryption_roundtrip(svc):
    enc = svc._encrypt_token('secret')
    assert svc._decrypt_token(enc) == 'secret'
    # corrupt token -> raw fallback
    assert svc._decrypt_token('not-encrypted') == 'not-encrypted'


def test_svc_encrypt_no_cipher():
    svc = make_service(creds=True)
    svc.cipher = None
    with pytest.raises(RuntimeError):
        svc._encrypt_token('t')
    assert svc._decrypt_token('xyz') == 'xyz'  # no cipher -> passthrough


def test_svc_generate_oauth_url(svc):
    svc.oauth_flow = MagicMock()
    svc.oauth_flow.authorization_url.return_value = ('https://auth?x=1', 'st')
    assert svc.generate_oauth_url('st', 'u1') == 'https://auth?x=1'
    svc.oauth_flow = None
    with pytest.raises(Exception):
        svc.generate_oauth_url('st', 'u1')


async def test_svc_exchange_code_success(svc, monkeypatch):
    creds = MagicMock(token='at', refresh_token='rt',
                      scopes=['s1'], expiry=DT)
    flow = MagicMock()
    flow.credentials = creds
    svc.oauth_flow = flow

    def fake_build(name, ver, credentials=None):
        b = MagicMock()
        if name == 'oauth2':
            b.userinfo().get().execute.return_value = {'id': 'u1'}
        else:
            b.spaces().list().execute.return_value = {
                'spaces': [{'name': 'spaces/S1', 'displayName': 'One',
                            'createTime': '2026-08-01T00:00:00Z'}]}
        return b

    monkeypatch.setattr(svc_mod, 'build', fake_build)
    svc._save_user_space = MagicMock(return_value=True)
    res = await svc.exchange_code_for_tokens('code', 'st')
    assert res['ok'] is True and res['spaces'][0]['space_id'] == 'spaces/S1'


async def test_svc_exchange_no_spaces_and_error(svc, monkeypatch):
    creds = MagicMock(token='at', refresh_token='rt', scopes=[], expiry=None)
    flow = MagicMock()
    flow.credentials = creds
    svc.oauth_flow = flow

    def fake_build(name, ver, credentials=None):
        b = MagicMock()
        if name == 'oauth2':
            b.userinfo().get().execute.return_value = {'id': 'u1'}
        else:
            b.spaces().list().execute.return_value = {'spaces': []}
        return b

    monkeypatch.setattr(svc_mod, 'build', fake_build)
    res = await svc.exchange_code_for_tokens('code', 'st')
    assert res['ok'] is False and 'No accessible spaces' in res['error']
    # no flow
    svc.oauth_flow = None
    res2 = await svc.exchange_code_for_tokens('code', 'st')
    assert res2['ok'] is False
    # generic exception
    svc.oauth_flow = MagicMock()
    svc.oauth_flow.fetch_token.side_effect = RuntimeError('x')
    res3 = await svc.exchange_code_for_tokens('code', 'st')
    assert res3['ok'] is False


# ============================================================================
# Enhanced service — chat service / space persistence
# ============================================================================

def test_svc_get_chat_service(svc, monkeypatch):
    # no space
    svc._get_user_space = MagicMock(return_value=None)
    assert svc._get_chat_service('nouser') is None
    # space without token
    sp = GoogleChatSpace(**{**SPACE_ROW, 'access_token': None})
    svc._get_user_space = MagicMock(return_value=sp)
    assert svc._get_chat_service('u1') is None
    # success
    svc._get_user_space = MagicMock(return_value=GoogleChatSpace(**SPACE_ROW))
    monkeypatch.setattr(svc_mod, 'build', MagicMock(return_value='built'))
    assert svc._get_chat_service('u1') == 'built'
    assert svc._get_chat_service('u1') == 'built'  # cached
    # build error
    svc.chat_services.clear()
    monkeypatch.setattr(svc_mod, 'build', MagicMock(side_effect=RuntimeError('x')))
    assert svc._get_chat_service('u1') is None


def test_svc_get_user_space_db_and_cache():
    db = FakeDB(rows=[dict(SPACE_ROW)])
    svc = make_service(db=db)
    assert svc._get_user_space('u1').space_id == 'spaces/S1'
    # redis cache path
    redis = MagicMock()
    redis.get.return_value = json.dumps(dict(SPACE_ROW))
    svc2 = make_service(redis_client=redis)
    assert svc2._get_user_space('u1').space_id == 'spaces/S1'
    # miss
    redis.get.return_value = None
    assert svc2._get_user_space('u1') is None
    # exception
    svc.db = MagicMock()
    svc.db.execute.side_effect = RuntimeError('db')
    assert svc._get_user_space('u1') is None


def test_svc_get_user_space_by_id_db_and_cache():
    db = FakeDB(rows=[dict(SPACE_ROW)])
    svc = make_service(db=db)
    svc._get_user_space_by_id = GoogleChatEnhancedService._get_user_space_by_id.__get__(svc)
    assert svc._get_user_space_by_id('spaces/S1').space_id == 'spaces/S1'
    redis = MagicMock()
    redis.get.return_value = json.dumps(dict(SPACE_ROW))
    svc2 = make_service(redis_client=redis)
    svc2._get_user_space_by_id = GoogleChatEnhancedService._get_user_space_by_id.__get__(svc2)
    assert svc2._get_user_space_by_id('spaces/S1').space_id == 'spaces/S1'
    redis.get.return_value = None
    assert svc2._get_user_space_by_id('nope') is None
    svc.db = MagicMock()
    svc.db.execute.side_effect = RuntimeError('db')
    assert svc._get_user_space_by_id('spaces/S1') is None


def test_svc_save_user_space_paths():
    db = MagicMock()
    svc = make_service(db=db)
    sp = GoogleChatSpace(**SPACE_ROW)
    assert svc._save_user_space(sp) is True
    db.execute.assert_called_once()
    db.commit.assert_called_once()
    assert svc.connection_status['spaces/S1'] == GoogleChatConnectionStatus.CONNECTED
    # redis path
    redis = MagicMock()
    svc2 = make_service(redis_client=redis)
    assert svc2._save_user_space(sp) is True
    redis.setex.assert_called_once()
    # no backend at all
    svc3 = make_service()
    assert svc3._save_user_space(sp) is True
    # exception
    svc.db = MagicMock()
    svc.db.execute.side_effect = RuntimeError('db')
    assert svc._save_user_space(sp) is False


# ============================================================================
# Enhanced service — connection test / spaces
# ============================================================================

async def test_svc_test_connection(svc, monkeypatch):
    cs = chat_service_mock(spaces_get={'name': 'spaces/S1', 'displayName': 'One',
                                       'type': 'ROOM',
                                       'spaceThreadingState': 'THREADING_ENABLED'})
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs))
    res = await svc.test_connection('spaces/S1')
    assert res['connected'] and res['space']['threaded'] is True
    # space missing
    svc._get_user_space_by_id = MagicMock(return_value=None)
    res2 = await svc.test_connection('nope')
    assert res2['connected'] is False
    # chat service missing
    svc._get_user_space_by_id = MagicMock(return_value=GoogleChatSpace(**SPACE_ROW))
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=None))
    res3 = await svc.test_connection('spaces/S1')
    assert res3['connected'] is False


async def test_svc_get_spaces():
    db = FakeDB(rows=[dict(SPACE_ROW)])
    svc = make_service(db=db)
    spaces = await svc.get_spaces('u1')
    assert spaces[0].space_id == 'spaces/S1'
    spaces_all = await svc.get_spaces()
    assert len(spaces_all) == 1
    # redis path
    redis = MagicMock()
    redis.keys.return_value = ['gc_space_user:u1']
    redis.get.return_value = json.dumps(dict(SPACE_ROW))
    svc2 = make_service(redis_client=redis)
    assert (await svc2.get_spaces('u1'))[0].space_id == 'spaces/S1'
    assert await svc2.get_spaces('other') == []
    # exception
    svc.db = MagicMock()
    svc.db.execute.side_effect = RuntimeError('db')
    assert await svc.get_spaces('u1') == []


# ============================================================================
# Enhanced service — send / list / search messages
# ============================================================================

async def test_svc_send_message(svc, monkeypatch):
    cs = chat_service_mock(messages_create={
        'name': 'spaces/S1/messages/M1', 'createTime': '2026-08-12T00:00:00Z',
        'thread': {'name': 'spaces/S1/threads/T1'}})
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs))
    res = await svc.send_message('spaces/S1', 'hello', thread_id='T1')
    assert res['ok'] and res['message_id'] == 'spaces/S1/messages/M1'
    # without thread, with db update
    svc.db = MagicMock()
    res2 = await svc.send_message('spaces/S1', 'hi', message_format='MARKDOWN',
                                  card_v2=[{'cardId': 'c'}])
    assert res2['ok'] and svc.db.execute.called
    # rate limited
    svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    res3 = await svc.send_message('spaces/S1', 'x')
    assert res3['ok'] is False
    # space not found
    svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    svc._get_user_space_by_id = MagicMock(return_value=None)
    assert (await svc.send_message('spaces/S1', 'x'))['ok'] is False
    # chat service failure
    svc._get_user_space_by_id = MagicMock(return_value=GoogleChatSpace(**SPACE_ROW))
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=None))
    assert (await svc.send_message('spaces/S1', 'x'))['ok'] is False
    # API returns nothing
    monkeypatch.setattr(svc, '_get_chat_service',
                        MagicMock(return_value=chat_service_mock(messages_create=None)))
    assert (await svc.send_message('spaces/S1', 'x'))['ok'] is False


async def test_svc_get_space_messages(svc, monkeypatch):
    msg = {'name': 'spaces/S1/messages/M1', 'text': 'hi',
           'sender': {'name': 'users/U1', 'displayName': 'Alice',
                      'email': 'a@x.com', 'type': 'HUMAN'},
           'thread': {'name': 'threads/T1'},
           'createTime': '2026-08-12T00:00:00Z',
           'lastModifiedTime': '2026-08-12T01:00:00Z',
           'cardsV2': [{'cardId': 'c'}], 'annotations': [{'type': 'x'}],
           'attachment': [{'name': 'f'}], 'arguments': ['a'],
           'reactions': [{'emoji': '👍'}]}
    cs = chat_service_mock(messages_list={'messages': [msg]})
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs))
    redis = MagicMock()
    svc.redis_client = redis
    msgs = await svc.get_space_messages('spaces/S1', limit=10, page_token='pt',
                                        filter='f')
    assert msgs[0].message_id == 'spaces/S1/messages/M1'
    assert msgs[0].is_edited is True
    assert redis.setex.called
    # empty response
    monkeypatch.setattr(svc, '_get_chat_service',
                        MagicMock(return_value=chat_service_mock(messages_list=None)))
    # messages_list=None -> execute returns MagicMock, truthy; force via raising
    cs2 = MagicMock()
    cs2.spaces().messages().list().execute.return_value = None
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs2))
    assert await svc.get_space_messages('spaces/S1') == []
    # error path with cache fallback
    svc._get_user_space_by_id = MagicMock(side_effect=RuntimeError('x'))
    cached = [json.loads(json.dumps({'message_id': 'M2', 'text': 't', 'user_id': 'u',
                                     'user_name': 'n', 'user_email': 'e',
                                     'space_id': 's', 'timestamp': 'ts'}))]
    redis.get.return_value = json.dumps(cached)
    msgs2 = await svc.get_space_messages('spaces/S1')
    assert msgs2[0].message_id == 'M2'
    # error path without cache
    redis.get.return_value = None
    assert await svc.get_space_messages('spaces/S1') == []


async def test_svc_search_messages(svc, monkeypatch):
    msg = {'name': 'M1', 'text': 'found', 'createTime': '2026-08-12T00:00:00Z',
           'sender': {'name': 'users/U1', 'displayName': 'A'}}
    cs = chat_service_mock(messages_list={'messages': [msg], 'nextPageToken': 'np'})
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs))
    res = await svc.search_messages('spaces/S1', 'found')
    assert res['ok'] and res['total'] == 1 and res['next_page_token'] == 'np'
    # empty response
    cs2 = MagicMock()
    cs2.spaces().messages().list().execute.return_value = None
    monkeypatch.setattr(svc, '_get_chat_service', MagicMock(return_value=cs2))
    res2 = await svc.search_messages('spaces/S1', 'q')
    assert res2['ok'] and res2['total'] == 0
    # error
    svc.rate_limiter.check_limit = AsyncMock(side_effect=RuntimeError('x'))
    res3 = await svc.search_messages('spaces/S1', 'q')
    assert res3['ok'] is False


# ============================================================================
# Enhanced service — info / capabilities / operations / lifecycle
# ============================================================================

async def test_svc_info_caps_health_close(svc):
    info = await svc.get_service_info()
    assert info['name'] == 'Google Chat Enhanced Service'
    assert info['status']['encryption_enabled'] is True
    caps = svc.get_capabilities()
    assert caps['supports_webhooks'] is True and len(caps['operations']) == 3
    assert svc.health_check()['healthy'] is True
    no_creds = make_service(creds=True)
    no_creds.client_id = None
    assert no_creds.health_check()['healthy'] is False
    redis = MagicMock()
    svc.redis_client = redis
    await svc.close()
    redis.close.assert_called_once()


async def test_svc_execute_operation(svc, monkeypatch):
    svc.send_message = AsyncMock(return_value={'ok': True})
    res = await svc.execute_operation('send_message',
                                      {'space_id': 's', 'text': 't'})
    assert res['success'] is True
    svc.get_space_messages = AsyncMock(return_value=[])
    res2 = await svc.execute_operation('get_space_messages', {'space_id': 's'})
    assert res2['success'] is True
    svc.search_messages = AsyncMock(return_value={'ok': True})
    res3 = await svc.execute_operation('search_messages',
                                       {'space_id': 's', 'query': 'q'})
    assert res3['success'] is True
    # unknown op
    res4 = await svc.execute_operation('bogus', {})
    assert res4['success'] is False and 'Unknown operation' in res4['error']
    # tenant mismatch
    res5 = await svc.execute_operation(
        'send_message', {'space_id': 's', 'text': 't'},
        context={'tenant_id': 'other'})
    assert res5['success'] is False and res5['error'] == 'Tenant mismatch'
    # exception
    svc.send_message = AsyncMock(side_effect=RuntimeError('x'))
    res6 = await svc.execute_operation('send_message',
                                       {'space_id': 's', 'text': 't'})
    assert res6['success'] is False


# ============================================================================
# Rate limiter
# ============================================================================

async def test_rate_limiter_local():
    rl = GoogleChatRateLimiter()
    for _ in range(10):
        assert await rl.check_limit('s', 'unknown_endpoint') is True
    assert await rl.check_limit('s', 'unknown_endpoint') is False  # limit 10
    # window reset
    rl.local_limits['gc_rate:s:unknown_endpoint']['reset'] = 0
    assert await rl.check_limit('s', 'unknown_endpoint') is True


async def test_rate_limiter_redis():
    redis = MagicMock()
    redis.get.return_value = '100'
    rl = GoogleChatRateLimiter(redis_client=redis)
    assert await rl.check_limit('s', 'messages_send') is False  # at limit
    redis.get.return_value = '5'
    assert await rl.check_limit('s', 'messages_send') is True
    assert redis.pipeline().incr.called
