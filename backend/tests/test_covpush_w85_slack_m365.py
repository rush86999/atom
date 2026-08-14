# -*- coding: utf-8 -*-
"""Coverage wave 85 — integrations.slack_analytics_engine,
integrations.slack_enhanced_service, integrations.microsoft365_service.

No network, no LLM spend: all HTTP is mocked at module boundaries
(aiohttp.ClientSession, httpx.AsyncClient, slack_sdk clients), and the
analytics engine's LLM service is replaced with AsyncMocks.
"""
import hashlib
import hmac
import json
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.slack_analytics_engine import (
    AnalyticsDataPoint,
    AnalyticsGranularity,
    AnalyticsMetric,
    AnalyticsReport,
    AnalyticsTimeRange,
    SlackAnalyticsEngine,
)
from integrations.slack_enhanced_service import (
    SlackChannel,
    SlackConnectionStatus,
    SlackEnhancedService,
    SlackEventType,
    SlackFile,
    SlackMessage,
    SlackRateLimiter,
    SlackWorkspace,
)
from integrations.microsoft365_service import Microsoft365Service
from slack_sdk.errors import SlackApiError


# ============================================================================
# Helpers
# ============================================================================

class FakeRedis:
    def __init__(self):
        self.store = {}
        self.lists = defaultdict(list)

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value

    def keys(self, pattern):
        prefix = pattern.rstrip("*")
        return [k for k in self.store if k.startswith(prefix)]

    def lpush(self, key, value):
        self.lists[key].insert(0, value)

    def ltrim(self, key, start, end):
        self.lists[key] = self.lists[key][start:end + 1]

    def close(self):
        pass


def _pt(value, ts=None, **dims):
    return AnalyticsDataPoint(
        timestamp=ts or datetime(2026, 8, 10, i_hour(), tzinfo=timezone.utc),
        metric=AnalyticsMetric.MESSAGE_VOLUME,
        value=value,
        dimensions=dims,
    )


_hour_counter = [0]


def i_hour():
    _hour_counter[0] += 1
    return _hour_counter[0] % 24


def _raw(n=4, **extra):
    base = datetime(2026, 8, 10, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        row = {
            'timestamp': (base + timedelta(hours=i)).isoformat(),
            'workspace_id': 'ws1',
            'channel_id': 'C1',
            'user_id': f'U{i % 2}',
            'text': f'message {i}',
        }
        row.update(extra)
        out.append(row)
    return out


@pytest.fixture()
def fake_redis():
    return FakeRedis()


# ============================================================================
# SlackAnalyticsEngine — construction & helpers
# ============================================================================

@pytest.fixture()
def engine(fake_redis):
    with patch('integrations.slack_analytics_engine.get_llm_service') as g:
        g.return_value = MagicMock()
        eng = SlackAnalyticsEngine({'database': None,
                                    'redis_client': fake_redis})
    return eng


def test_engine_init_flags(engine):
    assert engine.processors[AnalyticsMetric.MESSAGE_VOLUME]
    assert engine.cache_ttl == 300


def test_parse_timestamp_variants(engine):
    assert engine._parse_timestamp(None) is None
    assert engine._parse_timestamp('') is None
    dt = engine._parse_timestamp('1723300000')
    assert dt is not None
    dt2 = engine._parse_timestamp('2026-08-10T12:00:00+00:00')
    assert dt2.hour == 12
    dt3 = engine._parse_timestamp('2026-08-10 12:00:00')
    assert dt3.hour == 12
    assert engine._parse_timestamp('not-a-date') is None


def test_generate_cache_key(engine):
    key = engine._generate_cache_key(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS,
        AnalyticsGranularity.HOUR, {'a': 1}, 'ws', ['C2', 'C1'], ['U1'])
    assert 'message_volume' in key and 'C1,C2' in key


def test_get_date_ranges(engine):
    now = datetime.now(timezone.utc)
    assert engine._get_date_range(AnalyticsTimeRange.TODAY)[0].hour == 0
    s, e = engine._get_date_range(AnalyticsTimeRange.YESTERDAY)
    assert s.day != now.day or s < now
    assert engine._get_date_range(AnalyticsTimeRange.LAST_7_DAYS)[0] < now
    assert engine._get_date_range(AnalyticsTimeRange.LAST_30_DAYS)[0] < now
    assert engine._get_date_range(AnalyticsTimeRange.LAST_90_DAYS)[0] < now
    assert engine._get_date_range(AnalyticsTimeRange.CUSTOM)[0] < now


def test_build_query(engine):
    q = engine._build_query(AnalyticsMetric.MESSAGE_VOLUME, *([datetime.now()] * 2),
                            None, None, None, None)
    assert 'slack_messages' in q


def test_sentiment_distribution(engine):
    assert engine._get_sentiment_distribution([]) == {
        'positive': 0, 'neutral': 0, 'negative': 0}
    d = engine._get_sentiment_distribution([0.5, -0.5, 0.0])
    assert d == {'positive': 1 / 3, 'neutral': 1 / 3, 'negative': 1 / 3}


def test_calculate_score(engine):
    assert engine._calculate_score([]) == 0
    pts = [_pt(1), _pt(3)]
    assert engine._calculate_score(pts) == pytest.approx(2 / 3)
    assert engine._calculate_score(pts, reverse=True) == pytest.approx(1 / 3)


def test_calculate_trends(engine):
    pts_up = [_pt(v, ts=datetime(2026, 8, d, tzinfo=timezone.utc))
              for v, d in ((1, 1), (1, 1), (5, 2), (5, 2))]
    pts_flat = [_pt(2, ts=datetime(2026, 8, d, tzinfo=timezone.utc)) for d in (1, 1, 2, 2)]
    pts_down = [_pt(v, ts=datetime(2026, 8, d, tzinfo=timezone.utc))
                for v, d in ((5, 1), (5, 1), (1, 2), (1, 2))]
    t = engine._calculate_trends([
        ('message_volume', pts_up[:1]),  # insufficient
        ('engagement', pts_flat),
        ('collaboration', pts_up),
        ('response_time', pts_down),
    ])
    assert t['message_volume_trend'] == 'insufficient_data'
    assert t['engagement_trend'] == 'stable'
    assert t['collaboration_trend'] == 'increasing'
    assert t['response_time_trend'] == 'decreasing'
    assert 'collaboration_change_percent' in t


def test_training_corpus_helpers(engine):
    engine.add_training_texts(['a', 'b'], [datetime.now(timezone.utc)])
    engine.add_training_texts(['c'] * 60)
    info = engine.get_training_corpus_size()
    assert info['total_texts'] == 62
    assert info['timestamps_available'] is True
    assert info['can_train_lda'] is True


def test_train_lda_model(engine):
    result = engine.train_lda_model(['cat dog fish bird snake lion'] * 10, num_topics=2)
    assert 'success' in result
    if result['success']:
        assert result['num_documents'] == 10
        assert len(result['topic_words']) == 2


def test_train_lda_model_error(engine):
    result = engine.train_lda_model(['only one doc'])
    assert result['success'] is False
    assert result['error']


# ============================================================================
# SlackAnalyticsEngine — sentiment / topics
# ============================================================================

@pytest.mark.parametrize('text', ['', None])
async def test_analyze_sentiment_empty(engine, text):
    assert (await engine._analyze_sentiment(text))['method'] == 'empty'


async def test_analyze_sentiment_llm(engine):
    engine.llm_service = MagicMock()
    engine.llm_service.generate_structured = AsyncMock(
        return_value=MagicMock(score=0.9, confidence=0.99, label='positive'))
    res = await engine._analyze_sentiment('great job')
    assert res['score'] == 0.9 and res['method'] == 'llm_service'


async def test_analyze_sentiment_fallback(engine):
    engine.llm_service = MagicMock()
    engine.llm_service.generate_structured = AsyncMock(side_effect=RuntimeError('boom'))
    res = await engine._analyze_sentiment('whatever text')
    assert res['method'] in ('vader', 'fallback')
    assert 'score' in res


@pytest.mark.parametrize('text', ['', None])
async def test_extract_topics_empty(engine, text):
    assert (await engine._extract_topics(text))['method'] == 'empty'


async def test_extract_topics_llm_and_fallback(engine):
    engine.llm_service = MagicMock()
    engine.llm_service.generate_structured = AsyncMock(
        return_value=MagicMock(topics=['a', 'b'], confidence=0.8))
    assert (await engine._extract_topics('text'))['topics'] == ['a', 'b']

    engine.llm_service.generate_structured = AsyncMock(side_effect=RuntimeError('x'))
    res = await engine._extract_topics('hello #deploy #launch')
    assert set(res['topics']) == {'deploy', 'launch'}


# ============================================================================
# SlackAnalyticsEngine — processors
# ============================================================================

async def test_process_message_volume(engine):
    pts = await engine._process_message_volume(_raw(6), AnalyticsGranularity.HOUR)
    assert len(pts) == 6 and pts[0].value == 1
    pts_day = await engine._process_message_volume(_raw(48), AnalyticsGranularity.DAY)
    assert len(pts_day) == 2 and pts_day[0].value == 24
    pts_raw = await engine._process_message_volume(_raw(3), AnalyticsGranularity.MINUTE)
    assert len(pts_raw) == 3


async def test_process_user_activity(engine):
    raw = _raw(6)
    pts = await engine._process_user_activity(raw, AnalyticsGranularity.HOUR)
    assert pts and all(p.dimensions['user_id'] for p in pts)
    pts_d = await engine._process_user_activity(_raw(3), AnalyticsGranularity.DAY)
    assert len(pts_d) == 2  # two users within one day
    # items without user/timestamp skipped
    pts2 = await engine._process_user_activity(
        [{'timestamp': None}, {'user_id': 'U1'}], AnalyticsGranularity.HOUR)
    assert pts2 == []


async def test_process_engagement(engine):
    raw = _raw(2, reactions=[{'name': 'thumbsup', 'count': 2}],
               reply_count=1, mentions=['U2'])
    pts = await engine._process_engagement(raw, AnalyticsGranularity.DAY)
    assert len(pts) == 1
    # two messages: reactions 2*1 + replies 2*2 + mentions 2*3 = 12
    assert pts[0].value == 12


async def test_process_response_time(engine):
    raw = _raw(2, response_time_seconds=10)
    raw[1]['response_time_seconds'] = 20
    raw.append({'timestamp': raw[0]['timestamp']})  # no rt -> excluded
    pts = await engine._process_response_time(raw, AnalyticsGranularity.DAY)
    assert len(pts) == 1 and pts[0].value == 15
    assert pts[0].dimensions['min_response_time'] == 10


async def test_process_sentiment(engine):
    engine._analyze_sentiment = AsyncMock(
        side_effect=[{'score': 0.6}, {'score': -0.2}])
    raw = _raw(2)
    pts = await engine._process_sentiment(raw, AnalyticsGranularity.DAY)
    assert len(pts) == 1 and pts[0].value == pytest.approx(0.2)
    # no text -> no points
    pts2 = await engine._process_sentiment(
        [{'timestamp': '2026-08-10T00:00:00+00:00', 'text': ''}],
        AnalyticsGranularity.DAY)
    assert pts2 == []


async def test_process_collaboration(engine):
    raw = _raw(1, thread_ts='123', files=[{'id': 'f'}], mentions=['U9', 'U8'])
    pts = await engine._process_collaboration(raw, AnalyticsGranularity.DAY)
    assert pts[0].value == 2 + 1 + 3  # thread*2 + file*1 + mentions*1.5*2


async def test_process_productivity(engine):
    raw = _raw(1, text='task done, decision made and agreed')
    pts = await engine._process_productivity(raw, AnalyticsGranularity.DAY)
    assert pts[0].value == 3 + 5


async def test_process_topics(engine):
    engine._extract_topics = AsyncMock(
        side_effect=[{'topics': ['a', 'b']}, {'topics': ['b']}])
    pts = await engine._process_topics(_raw(2), AnalyticsGranularity.DAY)
    assert len(pts) == 1
    assert pts[0].dimensions['topic_frequency'] == {'a': 1, 'b': 2}


async def test_process_reactions(engine):
    raw = _raw(1, reactions=[{'name': 'eyes', 'count': 3}, {'name': 'tada', 'count': 1}])
    pts = await engine._process_reactions(raw, AnalyticsGranularity.DAY)
    assert pts[0].value == 4 and pts[0].dimensions['unique_reactions'] == 2


async def test_process_file_sharing(engine):
    raw = _raw(1, files=[{'filetype': 'pdf', 'size': 100},
                         {'filetype': 'pdf', 'size': 50}])
    pts = await engine._process_file_sharing(raw, AnalyticsGranularity.DAY)
    assert pts[0].value == 2
    assert pts[0].dimensions['average_file_size'] == 75
    empty = await engine._process_file_sharing(
        [{'timestamp': '2026-08-10T00:00:00+00:00'}], AnalyticsGranularity.DAY)
    assert empty[0].dimensions['average_file_size'] == 0


# ============================================================================
# SlackAnalyticsEngine — get_analytics / cache / mock data
# ============================================================================

async def test_get_analytics_with_cache(engine):
    engine._fetch_data = AsyncMock(return_value=_raw(6))
    first = await engine.get_analytics(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS,
        AnalyticsGranularity.HOUR)
    assert len(first) == 6
    again = await engine.get_analytics(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS,
        AnalyticsGranularity.HOUR)
    assert len(again) == 6
    assert engine._fetch_data.await_count == 1  # second hit came from cache


async def test_get_analytics_error(engine):
    engine._fetch_data = AsyncMock(side_effect=RuntimeError('db down'))
    assert await engine.get_analytics(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY) == []


async def test_fetch_data_db_and_error(engine):
    engine.database = MagicMock()
    engine.database.execute.return_value.fetchall.return_value = [
        {'timestamp': '2026-08-10T00:00:00+00:00', 'value': 5}]
    rows = await engine._fetch_data(AnalyticsMetric.MESSAGE_VOLUME,
                                    AnalyticsTimeRange.TODAY, None, None, None, None)
    assert rows == [{'timestamp': '2026-08-10T00:00:00+00:00', 'value': 5}]

    engine.database.execute.side_effect = RuntimeError('boom')
    assert await engine._fetch_data(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY, None,
        None, None, None) == []


async def test_fetch_data_generates_mock(engine):
    rows = await engine._fetch_data(AnalyticsMetric.RESPONSE_TIME,
                                    AnalyticsTimeRange.TODAY, None, None, None, None)
    assert rows and 'value' in rows[0]


# ============================================================================
# SlackAnalyticsEngine — insights / reports / top items
# ============================================================================

async def test_get_insights_all_metrics(engine):
    day = datetime(2026, 8, 10, tzinfo=timezone.utc)
    vol = [AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.MESSAGE_VOLUME,
                              value=10, dimensions={'user_id': 'U1', 'channel_id': 'C1'})]
    for metric in (AnalyticsMetric.MESSAGE_VOLUME, AnalyticsMetric.USER_ACTIVITY,
                   AnalyticsMetric.ENGAGEMENT, AnalyticsMetric.RESPONSE_TIME,
                   AnalyticsMetric.SENTIMENT, AnalyticsMetric.TOPICS):
        engine.get_analytics = AsyncMock(return_value=vol)
        res = await engine.get_insights(metric, AnalyticsTimeRange.LAST_7_DAYS)
        assert res and res['metric'] == metric.value

    engine.get_analytics = AsyncMock(return_value=[])
    assert await engine.get_insights(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS) == {}

    engine.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert await engine.get_insights(
        AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.LAST_7_DAYS) == {}


async def test_sentiment_insight_labels(engine):
    for val, label in ((0.5, 'positive'), (-0.5, 'negative'), (0.0, 'neutral')):
        day = datetime(2026, 8, 10, tzinfo=timezone.utc)
        engine.get_analytics = AsyncMock(return_value=[
            AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.SENTIMENT,
                               value=val)])
        res = await engine.get_insights(
            AnalyticsMetric.SENTIMENT, AnalyticsTimeRange.TODAY)
        assert res['dominant_sentiment'] == label


async def test_generate_report(engine):
    report = AnalyticsReport(
        id='r1', name='Report', description='d',
        metrics=[AnalyticsMetric.MESSAGE_VOLUME],
        time_range=AnalyticsTimeRange.LAST_7_DAYS,
        granularity=AnalyticsGranularity.DAY, created_by='me')
    engine.reports['r1'] = report
    day = datetime(2026, 8, 10, tzinfo=timezone.utc)
    engine.get_analytics = AsyncMock(return_value=[
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.MESSAGE_VOLUME,
                           value=5)])
    engine.get_insights = AsyncMock(return_value={'a': 1})
    out = await engine.generate_report('r1')
    assert out['id'] == 'r1' and out['metrics'][0]['name'] == 'message_volume'

    assert (await engine.generate_report('missing'))['error']

    # per-metric error branch
    engine.get_analytics = AsyncMock(side_effect=RuntimeError('bad'))
    out2 = await engine.generate_report('r1')
    assert out2['metrics'][0]['error']


async def test_top_users_and_channels(engine):
    day = datetime(2026, 8, 10, tzinfo=timezone.utc)
    pts = [
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.USER_ACTIVITY,
                           value=5, dimensions={'user_id': 'U1', 'channel_id': 'C1'}),
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.USER_ACTIVITY,
                           value=3, dimensions={'user_id': 'U1', 'channel_id': 'C1'}),
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.USER_ACTIVITY,
                           value=9, dimensions={'user_id': 'U2', 'channel_id': 'C2'}),
    ]
    engine.get_analytics = AsyncMock(return_value=pts)
    users = await engine.get_top_users(AnalyticsMetric.USER_ACTIVITY,
                                       AnalyticsTimeRange.LAST_7_DAYS)
    assert users[0]['user_id'] == 'U2' and users[0]['total_value'] == 9
    chans = await engine.get_top_channels(AnalyticsMetric.USER_ACTIVITY,
                                          AnalyticsTimeRange.LAST_7_DAYS)
    assert chans[0]['total_value'] in (8, 9)

    engine.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert await engine.get_top_users(AnalyticsMetric.USER_ACTIVITY,
                                      AnalyticsTimeRange.TODAY) == []
    assert await engine.get_top_channels(AnalyticsMetric.USER_ACTIVITY,
                                         AnalyticsTimeRange.TODAY) == []


async def test_trending_topics(engine):
    day = datetime(2026, 8, 10, tzinfo=timezone.utc)
    pts = [
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.TOPICS,
                           value=['deploy', 'launch']),
        AnalyticsDataPoint(timestamp=day, metric=AnalyticsMetric.TOPICS,
                           value='deploy, testing'),
    ]
    engine.get_analytics = AsyncMock(return_value=pts)
    topics = await engine.get_trending_topics(AnalyticsTimeRange.LAST_7_DAYS)
    assert topics[0] == {'topic': 'deploy', 'mentions': 2}

    engine.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert await engine.get_trending_topics(AnalyticsTimeRange.TODAY) == []


async def test_engagement_heatmap(engine):
    base = datetime(2026, 8, 10, 14, tzinfo=timezone.utc)
    pts = [AnalyticsDataPoint(timestamp=base + timedelta(hours=h),
                              metric=AnalyticsMetric.ENGAGEMENT, value=h + 1)
           for h in range(3)]
    engine.get_analytics = AsyncMock(return_value=pts)
    hm = await engine.get_engagement_heatmap(AnalyticsTimeRange.LAST_7_DAYS)
    assert len(hm['heatmap']) == 7
    day_name = base.strftime('%A')
    day = next(d for d in hm['heatmap'] if d['day'] == day_name)
    assert day['hours'][16]['normalized'] == 1.0
    assert hm['max_value'] == 3

    engine.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert await engine.get_engagement_heatmap(AnalyticsTimeRange.TODAY) == {}


async def test_predict_message_volume_insufficient(engine):
    engine.get_analytics = AsyncMock(return_value=[])
    res = await engine.predict_message_volume()
    assert res == {'error': 'Insufficient historical data for prediction'}


async def test_predict_message_volume_full(engine):
    now = datetime.now(timezone.utc)
    pts = [AnalyticsDataPoint(
        timestamp=now - timedelta(hours=i), metric=AnalyticsMetric.MESSAGE_VOLUME,
        value=10) for i in range(168)]
    engine.get_analytics = AsyncMock(return_value=pts)
    res = await engine.predict_message_volume(hours_ahead=3)
    assert len(res['predictions']) == 3
    assert res['model_used'] == 'ai_enhanced_moving_average'
    assert res['confidence_score'] == 0.85


async def test_productivity_metrics(engine):
    day = datetime(2026, 8, 10, tzinfo=timezone.utc)

    def mk(v):
        return [AnalyticsDataPoint(timestamp=day,
                                   metric=AnalyticsMetric.MESSAGE_VOLUME, value=v)]

    engine.get_analytics = AsyncMock(
        side_effect=[mk(5), mk(2), mk(5)])
    res = await engine.get_productivity_metrics(AnalyticsTimeRange.LAST_7_DAYS)
    assert 'overall_productivity' in res and 'trends' in res

    engine.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert await engine.get_productivity_metrics(AnalyticsTimeRange.TODAY) == {}


# ============================================================================
# SlackEnhancedService — models, oauth, tokens
# ============================================================================

@pytest.fixture()
def slack_svc():
    return SlackEnhancedService(tenant_id='default', config={})


def _ws(team_id='T1', token='xoxb-token'):
    return SlackWorkspace(team_id=team_id, team_name='Team', domain='team',
                          url='https://team.slack.com', access_token=token)


def test_slack_models_defaults():
    ws = _ws()
    assert ws.scopes == [] and ws.settings == {}
    ch = SlackChannel(channel_id='C1', name='general')
    assert ch.created is not None
    msg = SlackMessage(message_id='1', text='hi <@U123> and <@W456>',
                       user_id='U', user_name='u', channel_id='C', channel_name='c',
                       workspace_id='T', timestamp='1')
    assert msg.reactions == [] and msg.mentions == []
    assert slack_svc_helper_mentions() == ['U123', 'W456']
    f = SlackFile(file_id='F1', name='a', title='a', mimetype='text/plain',
                  filetype='text', pretty_type='Text', size=1,
                  url_private='u', permalink='p', user_id='U', user_name='u',
                  timestamp='1723300000')
    assert f.created is not None


def slack_svc_helper_mentions():
    svc = SlackEnhancedService(tenant_id='t', config={})
    return svc._extract_mentions('hi <@U123> and <@W456>')


def test_encrypt_decrypt_roundtrip():
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    svc = SlackEnhancedService(tenant_id='t', config={'encryption_key': key})
    assert svc.cipher is not None
    assert svc._decrypt_token(svc._encrypt_token('secret')) == 'secret'
    # without cipher it's a passthrough
    assert slack_svc_configless_encrypt() == 'plain'


def slack_svc_configless_encrypt():
    svc = SlackEnhancedService(tenant_id='t', config={})
    return svc._encrypt_token('plain')


def test_invalid_encryption_key(caplog):
    svc = SlackEnhancedService(tenant_id='t', config={'encryption_key': 'nope'})
    assert svc.cipher is None


def test_generate_oauth_url(slack_svc):
    url = slack_svc.generate_oauth_url('state123', 'U1')
    assert 'slack.com/oauth/v2/authorize' in url
    assert 'state=state123' in url
    url2 = slack_svc.generate_oauth_url('s', 'u', scopes=['chat:write'])
    assert 'chat:write' in url2


async def test_rate_limiter_local():
    rl = SlackRateLimiter()
    assert await rl.check_limit('ws', 'chat.postMessage') is True
    assert await rl.check_limit('ws', 'chat.postMessage') is False  # limit 1/sec
    # window expiry resets the local counter
    rl.local_limits['slack_rate:ws:chat.postMessage'] = {
        'count': 1, 'reset': time.time() - 2}
    assert await rl.check_limit('ws', 'chat.postMessage') is True


async def test_rate_limiter_redis():
    redis = MagicMock()
    redis.get.return_value = '5'
    rl = SlackRateLimiter(redis)
    assert await rl.check_limit('ws', 'chat.postMessage') is False
    redis.get.return_value = None
    pipe = MagicMock()
    redis.pipeline.return_value = pipe
    assert await rl.check_limit('ws', 'chat.postMessage') is True
    pipe.incr.assert_called()


def test_get_workspace_from_db():
    svc = SlackEnhancedService(tenant_id='t', config={})
    svc.db = MagicMock()
    svc.db.execute.return_value.fetchone.return_value = asdict_ws(_ws('T9'))
    ws = svc._get_workspace('T9')
    assert ws.team_id == 'T9'

    svc.db.execute.side_effect = RuntimeError('db down')
    assert svc._get_workspace('T9') is None


def asdict_ws(ws):
    from dataclasses import asdict
    return asdict(ws)


def ws_json(ws):
    return json.dumps(asdict_ws(ws), default=str)


def test_get_workspace_from_redis():
    svc = SlackEnhancedService(tenant_id='t', config={})
    svc.redis_client = FakeRedis()
    svc.redis_client.setex('workspace:T1', 10, ws_json(_ws('T1')))
    assert svc._get_workspace('T1').team_id == 'T1'
    assert svc._get_workspace('nope') is None


def test_get_workspace_from_token_storage():
    svc = SlackEnhancedService(tenant_id='t', config={})
    stored = {'team': {'id': 'T7', 'name': 'N', 'domain': 'd'},
              'access_token': 'tok', 'bot_user_id': 'B1',
              'authed_user': {'id': 'U1'}, 'scope': 'a,b'}
    with patch('integrations.slack_enhanced_service.token_storage') as ts:
        ts.get_token.return_value = stored
        ws = svc._get_workspace('T7')
    assert ws.team_id == 'T7' and ws.scopes == ['a', 'b']

    with patch('integrations.slack_enhanced_service.token_storage') as ts:
        ts.get_token.side_effect = RuntimeError('x')
        assert svc._get_workspace('T7') is None


def test_save_workspace_db_and_cache():
    svc = SlackEnhancedService(tenant_id='t', config={})
    svc.db = MagicMock()
    assert svc._save_workspace(_ws('T1')) is True
    svc.db.commit.assert_called()

    svc.db = None
    svc.redis_client = FakeRedis()
    assert svc._save_workspace(_ws('T2')) is True
    assert svc.redis_client.get('workspace:T2') is not None

    svc.redis_client.setex = MagicMock(side_effect=RuntimeError('x'))
    assert svc._save_workspace(_ws('T3')) is False


def test_get_client(slack_svc):
    slack_svc._get_workspace = MagicMock(return_value=_ws())
    client = slack_svc._get_client('T1')
    assert client is not None
    assert slack_svc._get_client('T1') is client  # cached
    sync = slack_svc._get_sync_client('T1')
    assert sync is not None

    # workspace lookup fails -> no client
    slack_svc._get_workspace = MagicMock(return_value=None)
    assert slack_svc._get_client('T2') is None
    assert slack_svc._get_sync_client('T2') is None

    # unexpected exception -> swallowed, returns None
    slack_svc._get_workspace = MagicMock(side_effect=RuntimeError('x'))
    assert slack_svc._get_client('T3') is None
    assert slack_svc._get_sync_client('T3') is None


# ============================================================================
# SlackEnhancedService — oauth exchange / connection
# ============================================================================

def _http_response(status=200, payload=None):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload or {}
    resp.text = 'body'
    return resp


async def test_exchange_code_success(slack_svc):
    payload = {'ok': True, 'access_token': 'xoxb', 'bot_user_id': 'B',
               'team': {'id': 'T1', 'name': 'Team', 'domain': 'team',
                        'icon': {'image_132': 'x'}},
               'enterprise': {'id': 'E', 'name': 'EN'},
               'authed_user': {'id': 'U1'}, 'scope': 'a,b'}
    slack_svc._save_workspace = MagicMock(return_value=True)
    with patch('integrations.slack_enhanced_service.httpx.AsyncClient') as cls:
        client = cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=_http_response(200, payload))
        result = await slack_svc.exchange_code_for_tokens('code', 'state')
    assert result['ok'] is True

    # save failure
    slack_svc._save_workspace = MagicMock(return_value=False)
    with patch('integrations.slack_enhanced_service.httpx.AsyncClient') as cls:
        client = cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=_http_response(200, payload))
        result = await slack_svc.exchange_code_for_tokens('code', 'state')
    assert result['ok'] is False and 'error' in result


async def test_exchange_code_failures(slack_svc):
    with patch('integrations.slack_enhanced_service.httpx.AsyncClient') as cls:
        client = cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=_http_response(500, {}))
        result = await slack_svc.exchange_code_for_tokens('c', 's')
    assert result['ok'] is False

    with patch('integrations.slack_enhanced_service.httpx.AsyncClient') as cls:
        client = cls.return_value.__aenter__.return_value
        client.post = AsyncMock(return_value=_http_response(200, {'ok': False, 'error': 'bad'}))
        result = await slack_svc.exchange_code_for_tokens('c', 's')
    assert result['ok'] is False

    with patch('integrations.slack_enhanced_service.httpx.AsyncClient') as cls:
        cls.return_value.__aenter__.side_effect = RuntimeError('net')
        result = await slack_svc.exchange_code_for_tokens('c', 's')
    assert result['ok'] is False


def _client_mock(**methods):
    client = MagicMock()
    for name, value in methods.items():
        setattr(client, name, AsyncMock(return_value=value))
    return client


async def test_test_connection_success(slack_svc):
    client = _client_mock(auth_test={'ok': True, 'team_id': 'T1', 'team': 'Team',
                                     'user_id': 'U1', 'user': 'u', 'bot_id': 'B'})
    slack_svc.clients['T1'] = client
    slack_svc._get_workspace = MagicMock(return_value=_ws())
    slack_svc._save_workspace = MagicMock(return_value=True)
    res = await slack_svc.test_connection('T1')
    assert res['connected'] is True
    assert slack_svc.connection_status['T1'] == SlackConnectionStatus.CONNECTED

    # no workspace to refresh -> still connected
    slack_svc._get_workspace = MagicMock(return_value=None)
    assert (await slack_svc.test_connection('T1'))['connected'] is True


async def test_test_connection_no_client(slack_svc):
    slack_svc._get_client = MagicMock(return_value=None)
    res = await slack_svc.test_connection('T1')
    assert res['connected'] is False and res['status'] == 'error'


async def test_test_connection_not_ok(slack_svc):
    client = _client_mock(auth_test={'ok': False, 'error': 'invalid_auth'})
    slack_svc.clients['T1'] = client
    res = await slack_svc.test_connection('T1')
    assert res['connected'] is False


def _slack_api_error(response):
    return SlackApiError('err', response=response)


async def test_test_connection_ratelimited_dict_response(slack_svc):
    client = MagicMock()
    client.auth_test = AsyncMock(side_effect=_slack_api_error(
        {'data': {'error': 'ratelimited'}, 'headers': {'Retry-After': 42}}))
    slack_svc.clients['T1'] = client
    res = await slack_svc.test_connection('T1')
    assert res['status'] == 'rate_limited' and res['retry_after'] == 42


async def test_test_connection_error_object_response(slack_svc):
    client = MagicMock()
    resp_obj = MagicMock()
    resp_obj.data = {'error': 'other'}
    resp_obj.headers = {'Retry-After': '7'}
    client.auth_test = AsyncMock(side_effect=_slack_api_error(resp_obj))
    slack_svc.clients['T1'] = client
    res = await slack_svc.test_connection('T1')
    assert res['status'] == 'error'

    client.auth_test = AsyncMock(side_effect=RuntimeError('boom'))
    res = await slack_svc.test_connection('T1')
    assert res['connected'] is False


# ============================================================================
# SlackEnhancedService — workspace/channel/message operations
# ============================================================================

async def test_get_workspaces(slack_svc):
    slack_svc.db = MagicMock()
    slack_svc.db.execute.return_value.fetchall.return_value = [asdict_ws(_ws('T1'))]
    assert (await slack_svc.get_workspaces())[0].team_id == 'T1'
    assert (await slack_svc.get_workspaces(user_id='U1'))[0].team_id == 'T1'

    slack_svc.db = None
    slack_svc.redis_client = FakeRedis()
    slack_svc.redis_client.setex('workspace:T2', 10, ws_json(_ws('T2')))
    assert (await slack_svc.get_workspaces())[0].team_id == 'T2'
    assert await slack_svc.get_workspaces(user_id='nobody') == []

    slack_svc.db = MagicMock()
    slack_svc.db.execute.side_effect = RuntimeError('x')
    assert await slack_svc.get_workspaces() == []


async def test_get_channels_success(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc.redis_client = FakeRedis()
    client = _client_mock(conversations_list={
        'ok': True, 'channels': [{
            'id': 'C1', 'name': 'general', 'purpose': {'value': 'p'},
            'topic': {'value': 't'}, 'is_private': True, 'is_general': True,
            'num_members': 5, 'created': 1723300000}]})
    slack_svc._get_client = MagicMock(return_value=client)
    chans = await slack_svc.get_channels('T1', include_private=True,
                                         include_archived=True)
    assert chans[0].channel_id == 'C1' and chans[0].is_private

    # error path with cached channels
    client.conversations_list = AsyncMock(side_effect=_slack_api_error(None))
    chans = await slack_svc.get_channels('T1')
    assert chans[0].channel_id == 'C1'

    # error path, no cache
    slack_svc.redis_client.store.pop('channels:T1')
    assert await slack_svc.get_channels('T1') == []


async def test_get_channels_failures(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert await slack_svc.get_channels('T1') == []

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert await slack_svc.get_channels('T1') == []

    slack_svc._get_client = MagicMock(side_effect=RuntimeError('boom'))
    assert await slack_svc.get_channels('T1') == []


async def test_send_message(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    res = await slack_svc.send_message('T1', 'C1', 'hi')
    assert res['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.send_message('T1', 'C1', 'hi'))['ok'] is False

    slack_svc.redis_client = FakeRedis()
    client = _client_mock(chat_postMessage={
        'ok': True, 'ts': '123.4', 'channel': 'C1',
        'message': {'ts': '123.4', 'text': 'hi'}})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.send_message('T1', 'C1', 'hi', thread_ts='1',
                                       blocks=[{'b': 1}], attachments=[{'a': 1}])
    assert res['ok'] is True

    client.chat_postMessage = AsyncMock(return_value={'ok': False, 'error': 'nope'})
    assert (await slack_svc.send_message('T1', 'C1', 'hi'))['ok'] is False

    client.chat_postMessage = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.send_message('T1', 'C1', 'hi'))['ok'] is False


async def test_get_channel_history(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert await slack_svc.get_channel_history('T1', 'C1') == []

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert await slack_svc.get_channel_history('T1', 'C1') == []

    slack_svc.redis_client = FakeRedis()
    client = _client_mock(conversations_history={
        'ok': True, 'messages': [{
            'ts': '1', 'text': 'hi <@U1>', 'user': 'U1', 'thread_ts': '0',
            'reply_count': 2, 'reactions': [{'name': 'x', 'count': 1}],
            'edited': {'ts': '2'}}]})
    slack_svc._get_client = MagicMock(return_value=client)
    msgs = await slack_svc.get_channel_history('T1', 'C1', include_threads=True)
    assert msgs[0].message_id == '1' and msgs[0].is_edited

    client.conversations_history = AsyncMock(side_effect=_slack_api_error(None))
    assert await slack_svc.get_channel_history('T1', 'C1') == []
    client.conversations_history = AsyncMock(side_effect=RuntimeError('x'))
    assert await slack_svc.get_channel_history('T1', 'C1') == []


async def test_upload_file(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.upload_file('T1', 'C1', '/tmp/f'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.upload_file('T1', 'C1', '/tmp/f'))['ok'] is False

    slack_svc.redis_client = FakeRedis()
    fd = {'id': 'F1', 'name': 'f.pdf', 'title': 'f', 'mimetype': 'application/pdf',
          'filetype': 'pdf', 'pretty_type': 'PDF', 'size': 10,
          'url_private': 'u', 'permalink': 'p', 'user': 'U1',
          'timestamp': 1723300000, 'is_public': True}
    client = _client_mock(files_upload_v2={'ok': True, 'file': fd})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.upload_file('T1', 'C1', '/tmp/f', title='f',
                                      initial_comment='c')
    assert res['ok'] is True and res['file']['file_id'] == 'F1'

    client.files_upload_v2 = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.upload_file('T1', 'C1', '/tmp/f'))['ok'] is False
    client.files_upload_v2 = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.upload_file('T1', 'C1', '/tmp/f'))['ok'] is False


async def test_search_messages(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.search_messages('T1', 'q'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.search_messages('T1', 'q'))['ok'] is False

    client = _client_mock(search_messages={
        'ok': True, 'messages': {'total': 1, 'paging': {'page': 1},
                                 'matches': [{'ts': '1', 'text': 'q',
                                              'channel': {'id': 'C1', 'name': 'c'},
                                              'score': 1.5}]}})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.search_messages('T1', 'q', channel_id='C1')
    assert res['ok'] is True and res['total'] == 1

    client.search_messages = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.search_messages('T1', 'q'))['ok'] is False
    client.search_messages = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.search_messages('T1', 'q'))['ok'] is False


async def test_add_reaction(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.add_reaction('T1', 'C1', '1', 'thumbsup'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.add_reaction('T1', 'C1', '1', ':thumbsup:'))['ok'] is False

    client = _client_mock(reactions_add={'ok': True})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.add_reaction('T1', 'C1', '1', ':thumbsup:')
    assert res['ok'] is True and res['reaction'] == 'thumbsup'

    client.reactions_add = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.add_reaction('T1', 'C1', '1', 'x'))['ok'] is False
    client.reactions_add = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.add_reaction('T1', 'C1', '1', 'x'))['ok'] is False


async def test_send_dm(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.send_dm('T1', 'U1', 'hi'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.send_dm('T1', 'U1', 'hi'))['ok'] is False

    client = MagicMock()
    client.conversations_open = AsyncMock(return_value={'ok': False, 'error': 'e'})
    slack_svc._get_client = MagicMock(return_value=client)
    assert (await slack_svc.send_dm('T1', 'U1', 'hi'))['ok'] is False

    client.conversations_open = AsyncMock(
        return_value={'ok': True, 'channel': {'id': 'D1'}})
    client.chat_postMessage = AsyncMock(
        return_value={'ok': True, 'message': {'ts': '5'}})
    res = await slack_svc.send_dm('T1', 'U1', 'hi', blocks=[{'b': 1}])
    assert res['ok'] is True and res['channel'] == 'D1'

    client.chat_postMessage = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.send_dm('T1', 'U1', 'hi'))['ok'] is False
    client.chat_postMessage = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.send_dm('T1', 'U1', 'hi'))['ok'] is False


async def test_create_channel(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.create_channel('T1', 'new'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.create_channel('T1', 'new'))['ok'] is False

    client = MagicMock()
    client.conversations_create = AsyncMock(
        return_value={'ok': True, 'channel': {'id': 'C9', 'name': 'new',
                                              'is_private': False, 'created': 1}})
    client.conversations_setTopic = AsyncMock(return_value={'ok': True})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.create_channel('T1', 'new', description='d')
    assert res['ok'] is True and client.conversations_setTopic.called

    client.conversations_create = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.create_channel('T1', 'new'))['ok'] is False
    client.conversations_create = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.create_channel('T1', 'new'))['ok'] is False


async def test_invite_to_channel(slack_svc):
    client = MagicMock()
    client.conversations_invite = AsyncMock(side_effect=[
        {'ok': True}, {'ok': False, 'error': 'already_in'}])
    slack_svc._get_client = MagicMock(return_value=client)
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    res = await slack_svc.invite_to_channel('T1', 'C1', ['U1', 'U2'])
    assert res['invited_users'] == ['U1'] and len(res['failed_users']) == 1

    client.conversations_invite = AsyncMock(
        side_effect=_slack_api_error(None))
    res = await slack_svc.invite_to_channel('T1', 'C1', ['U1'])
    assert res['ok'] is False and res['failed_users']

    slack_svc._get_client = MagicMock(return_value=None)
    res = await slack_svc.invite_to_channel('T1', 'C1', ['U1'])
    assert res['ok'] is False

    slack_svc._get_client = MagicMock(side_effect=RuntimeError('x'))
    assert 'error' in await slack_svc.invite_to_channel('T1', 'C1', ['U1'])


async def test_pin_message(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert (await slack_svc.pin_message('T1', 'C1', '1'))['ok'] is False

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.pin_message('T1', 'C1', '1'))['ok'] is False

    client = _client_mock(pins_add={'ok': True})
    slack_svc._get_client = MagicMock(return_value=client)
    assert (await slack_svc.pin_message('T1', 'C1', '1'))['ok'] is True

    client.pins_add = AsyncMock(return_value={'ok': False, 'error': 'e'})
    assert (await slack_svc.pin_message('T1', 'C1', '1'))['ok'] is False
    client.pins_add = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.pin_message('T1', 'C1', '1'))['ok'] is False


# ============================================================================
# SlackEnhancedService — webhooks & events
# ============================================================================

async def test_verify_webhook_signature(slack_svc):
    secret = 'signing-secret'
    svc = SlackEnhancedService(tenant_id='t', config={'signing_secret': secret})
    body = b'{"type":"event"}'
    ts = str(int(time.time()))
    basestring = f'v0:{ts}:{body.decode()}'
    sig = 'v0=' + hmac.new(secret.encode(), basestring.encode(),
                           hashlib.sha256).hexdigest()
    assert await svc.verify_webhook_signature(body, ts, sig) is True
    assert await svc.verify_webhook_signature(body, ts, 'v0=bad') is False
    old_ts = str(int(time.time()) - 1000)
    assert await svc.verify_webhook_signature(body, old_ts, sig) is False
    # no signing secret configured
    assert await slack_svc.verify_webhook_signature(body, ts, sig) is False
    # non-numeric timestamp -> exception path
    assert await svc.verify_webhook_signature(body, 'NaN', sig) is False


async def test_handle_webhook_event(slack_svc):
    slack_svc.redis_client = FakeRedis()
    called = []

    async def handler(event):
        called.append(event['event']['type'])

    async def bad_handler(event):
        raise RuntimeError('nope')

    async def webhook_handler(event):
        called.append('webhook')

    async def bad_webhook(event):
        raise RuntimeError('nope')

    slack_svc.register_event_handler(SlackEventType.MESSAGE, handler)
    slack_svc.register_event_handler(SlackEventType.MESSAGE, handler)  # dedupe
    slack_svc.register_webhook_handler(webhook_handler)
    slack_svc.register_webhook_handler(bad_webhook)

    res = await slack_svc.handle_webhook_event(
        {'event': {'type': 'message'}, 'team_id': 'T1'})
    assert res['ok'] is True
    assert called == ['message', 'webhook']
    assert 'slack_events:T1' in slack_svc.redis_client.lists

    # unknown event type still ok
    res = await slack_svc.handle_webhook_event(
        {'event': {'type': 'zzz'}, 'team_id': 'T1'})
    assert res['ok'] is True

    slack_svc.redis_client.lpush = MagicMock(side_effect=RuntimeError('x'))
    res = await slack_svc.handle_webhook_event(
        {'event': {'type': 'message'}, 'team_id': 'T1'})
    assert res['ok'] is False


async def test_cache_helpers(slack_svc):
    slack_svc.redis_client = FakeRedis()
    await slack_svc._cache_message('T1', {'ts': '1', 'text': 'x'})
    assert slack_svc.redis_client.get('message:T1:1') is not None

    msg = SlackMessage(message_id='1', text='t', user_id='U', user_name='u',
                       channel_id='C', channel_name='c', workspace_id='T',
                       timestamp='1')
    await slack_svc._cache_messages('T1', 'C1', [msg])
    assert slack_svc.redis_client.get('messages:T1:C1') is not None

    f = SlackFile(file_id='F', name='n', title='t', mimetype='m', filetype='f',
                  pretty_type='p', size=1, url_private='u', permalink='p',
                  user_id='U', user_name='u', timestamp='1723300000')
    await slack_svc._cache_file('T1', f)
    assert slack_svc.redis_client.get('file:T1:F') is not None

    # no redis -> no-op; redis failure -> logged not raised
    slack_svc.redis_client = None
    await slack_svc._cache_message('T1', {'ts': '1'})
    slack_svc.redis_client = MagicMock()
    slack_svc.redis_client.setex = MagicMock(side_effect=RuntimeError('x'))
    await slack_svc._cache_message('T1', {'ts': '1'})
    await slack_svc._cache_messages('T1', 'C1', [msg])
    await slack_svc._cache_file('T1', f)


def test_extract_mentions(slack_svc):
    assert slack_svc._extract_mentions('hi <@U1> <@W2> <@x3>') == ['U1', 'W2']


# ============================================================================
# SlackEnhancedService — info/analytics/sync/operations/close
# ============================================================================

async def test_service_info_and_capabilities(slack_svc):
    info = await slack_svc.get_service_info()
    assert info['name'] == 'Slack Enhanced Service'
    assert slack_svc.get_capabilities()['supports_webhooks'] is True
    assert len(slack_svc.get_operations()) == 5
    assert (await slack_svc.health_check())['healthy'] is True


async def test_get_analytics_dashboard(slack_svc):
    slack_svc.rate_limiter = MagicMock()
    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=False)
    assert 'error' in await slack_svc.get_analytics('T1')

    slack_svc.rate_limiter.check_limit = AsyncMock(return_value=True)
    slack_svc._get_client = MagicMock(return_value=None)
    assert (await slack_svc.get_analytics('T1'))['error'] == 'Not authenticated'

    client = MagicMock()
    client.conversations_list = AsyncMock(
        return_value={'ok': True, 'channels': [{'id': 'C1'}]})
    client.conversations_history = AsyncMock(
        return_value={'messages': [{}] * 3})
    slack_svc._get_client = MagicMock(return_value=client)
    res = await slack_svc.get_analytics('T1')
    assert res['channel_count'] == 1 and res['message_count'] == 60

    client.conversations_list = AsyncMock(side_effect=RuntimeError('x'))
    assert 'error' in await slack_svc.get_analytics('T1')


async def test_sync_to_postgres_cache(slack_svc, monkeypatch):
    slack_svc.get_analytics = AsyncMock(
        return_value={'error': 'x'})
    assert (await slack_svc.sync_to_postgres_cache('T1'))['success'] is False

    slack_svc.get_analytics = AsyncMock(
        return_value={'channel_count': 2, 'message_count': 10, 'active_users': 3})
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    db.commit = MagicMock()
    db.rollback = MagicMock()
    monkeypatch.setattr('core.database.SessionLocal', MagicMock(return_value=db))
    res = await slack_svc.sync_to_postgres_cache('T1')
    assert res == {'success': True, 'metrics_synced': 3}

    # update-existing path
    existing = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = existing
    assert (await slack_svc.sync_to_postgres_cache('T1'))['success'] is True

    # commit failure
    db.commit = MagicMock(side_effect=RuntimeError('x'))
    res = await slack_svc.sync_to_postgres_cache('T1')
    assert res['success'] is False

    # analytics raising
    slack_svc.get_analytics = AsyncMock(side_effect=RuntimeError('x'))
    assert (await slack_svc.sync_to_postgres_cache('T1'))['success'] is False


async def test_full_sync(slack_svc):
    slack_svc.sync_to_postgres_cache = AsyncMock(
        return_value={'success': True, 'metrics_synced': 3})
    res = await slack_svc.full_sync('ws', 'T1')
    assert res['success'] is True and res['team_id'] == 'T1'


async def test_execute_operation(slack_svc):
    res = await slack_svc.execute_operation('bogus', {})
    assert res['success'] is False

    res = await slack_svc.execute_operation('send_message', {'channel': None})
    assert res['success'] is False

    slack_svc.send_message = AsyncMock(side_effect=RuntimeError('x'))
    res = await slack_svc.execute_operation(
        'send_message', {'channel': 'C1', 'text': 'hi'})
    assert res['success'] is False

    slack_svc.send_message = AsyncMock(return_value={'ok': True})
    res = await slack_svc.execute_operation(
        'send_message', {'channel': 'C1', 'text': 'hi'})
    assert res['success'] is True

    slack_svc.send_message = AsyncMock(return_value={'ok': False, 'error': 'e'})
    res = await slack_svc.execute_operation(
        'send_message', {'channel': 'C1', 'text': 'hi'})
    assert res['success'] is False


async def test_close(slack_svc):
    aclient = MagicMock()
    aclient.close = AsyncMock()
    sclient = MagicMock()
    slack_svc.clients['T1'] = aclient
    slack_svc.sync_clients['T1'] = sclient
    slack_svc.redis_client = FakeRedis()
    await slack_svc.close()
    aclient.close.assert_awaited_once()
    sclient.close.assert_called_once()


# ============================================================================
# Microsoft365Service — graph request core
# ============================================================================

@pytest.fixture()
def m365():
    return Microsoft365Service(tenant_id='default', config={})


def _aiohttp_response(status=200, payload=None, text='err'):
    resp = MagicMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.json = AsyncMock(return_value=payload if payload is not None else {})
    return resp


def _install_aiohttp(monkeypatch, response, method='request'):
    session = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    setattr(session, method, MagicMock(return_value=ctx))
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=session)
    client.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr('aiohttp.ClientSession', MagicMock(return_value=client))
    return session


async def test_graph_request_success(m365, monkeypatch):
    _install_aiohttp(monkeypatch, _aiohttp_response(200, {'id': 'u1'}))
    res = await m365._make_graph_request('GET', 'https://x', 'tok')
    assert res == {'status': 'success', 'data': {'id': 'u1'}}


async def test_graph_request_204(m365, monkeypatch):
    _install_aiohttp(monkeypatch, _aiohttp_response(204))
    res = await m365._make_graph_request('DELETE', 'https://x', 'tok')
    assert res == {'status': 'success', 'data': None}


async def test_graph_request_error(m365, monkeypatch):
    _install_aiohttp(monkeypatch, _aiohttp_response(404, text='not found'))
    res = await m365._make_graph_request('GET', 'https://x', 'tok')
    assert res['status'] == 'error' and res['code'] == 404


async def test_graph_request_dev_bypass(m365, monkeypatch):
    monkeypatch.setenv('ATOM_ENV', 'development')
    res = await m365._make_graph_request('GET', 'https://x', 'fake_token')
    assert res['status'] == 'success'
    assert res['data']['mail'] == 'mock@example.com'


async def test_m365_health_and_caps(m365):
    assert m365.get_capabilities()[0] == 'send_message'
    assert (await m365.health_check())['status'] == 'unconfigured'
    svc = Microsoft365Service(tenant_id='t', config={'access_token': 'x'})
    assert (await svc.health_check())['status'] == 'healthy'


async def test_m365_authenticate(m365):
    res = await m365.authenticate('user-1')
    assert res['status'] == 'success'
    assert 'login.microsoftonline.com' in res['auth_url']
    assert res['state'] == 'microsoft365_user-1'
    assert (await m365._authenticate('u'))['state'] == 'microsoft365_u'


# ============================================================================
# Microsoft365Service — read endpoints via _make_graph_request
# ============================================================================

async def test_m365_read_endpoints(m365):
    m365._make_graph_request = AsyncMock(
        return_value={'status': 'success', 'data': {'id': 'x'}})
    assert (await m365.get_user_profile('t'))['data'] == {'id': 'x'}
    assert (await m365.list_teams('t'))['status'] == 'success'
    assert (await m365.list_channels('t', 'team1'))['status'] == 'success'
    assert (await m365.get_outlook_messages('t', 'inbox', 5))['status'] == 'success'
    assert (await m365.get_calendar_events('t', 's', 'e'))['status'] == 'success'
    assert (await m365.get_planner_tasks('t'))['status'] == 'success'
    assert (await m365.get_dynamics_deals('t'))['status'] == 'success'
    assert (await m365.get_dynamics_invoices('t'))['status'] == 'success'
    assert (await m365.get_service_status('t'))['status'] == 'success'


async def test_m365_read_endpoints_error(m365):
    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('net'))
    for coro in (m365.get_user_profile('t'), m365.list_teams('t'),
                 m365.list_channels('t', 'team'), m365.get_outlook_messages('t'),
                 m365.get_calendar_events('t', 's', 'e'),
                 m365.get_planner_tasks('t'), m365.get_dynamics_deals('t'),
                 m365.get_dynamics_invoices('t'), m365.get_service_status('t')):
        res = await coro
        assert res['status'] == 'error'


async def test_m365_execute_operation(m365):
    m365._authenticate = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_operation('authenticate', user_id='u'))['status'] == 'success'

    m365._send_message = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_operation(
        'send_message', team_id='t', channel_id='c', content='x'))['status'] == 'success'

    m365._list_teams = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_operation('list_teams'))['status'] == 'success'

    m365._list_channels = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_operation('list_channels', team_id='t'))['status'] == 'success'

    assert (await m365.execute_operation('nope'))['status'] == 'error'

    m365._list_teams = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.execute_operation('list_teams'))['status'] == 'error'


async def test_m365_private_helpers(m365):
    assert (await m365._send_message('t', 'c', 'x'))['status'] == 'error'
    assert (await m365._list_teams())['status'] == 'error'
    assert (await m365._list_channels('t'))['status'] == 'error'

    svc = Microsoft365Service(tenant_id='t', config={'access_token': 'tok'})
    svc._make_graph_request = AsyncMock(return_value={'status': 'success', 'data': {}})
    assert (await svc._send_message('t', 'c', 'x'))['status'] == 'success'
    assert (await svc._list_teams())['status'] == 'success'
    assert (await svc._list_channels('t'))['status'] == 'success'

    svc._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await svc._send_message('t', 'c', 'x'))['status'] == 'error'
    assert (await svc._list_teams())['status'] == 'error'
    assert (await svc._list_channels('t'))['status'] == 'error'


# ============================================================================
# Microsoft365Service — OneDrive actions
# ============================================================================

async def test_onedrive_list_files(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_onedrive_action(
        't', 'list_files', {'folder': 'docs'}))['status'] == 'success'
    m365._make_graph_request.assert_called_with(
        'GET',
        'https://graph.microsoft.com/v1.0/me/drive/root:/docs:/children?$top=100&$select=id,name,size,lastModifiedDateTime,file,folder',
        't')
    assert (await m365.execute_onedrive_action(
        't', 'list_files', {}))['status'] == 'success'


async def test_onedrive_get_content(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_onedrive_action(
        't', 'get_content', {'path': 'a.txt'}))['status'] == 'success'
    res = await m365.execute_onedrive_action('t', 'get_content', {})
    assert res['status'] == 'error' and 'path' in res['message']


async def test_onedrive_upload(m365, monkeypatch):
    session = _install_aiohttp(
        monkeypatch, _aiohttp_response(201, {'id': 'F1'}), method='put')
    res = await m365.execute_onedrive_action(
        't', 'upload', {'path': 'a.txt', 'file_content': b'data'})
    assert res['status'] == 'success'
    assert session.put.call_args.kwargs['data'] == b'data'

    _install_aiohttp(monkeypatch, _aiohttp_response(500), method='put')
    res = await m365.execute_onedrive_action(
        't', 'upload', {'path': 'a.txt', 'file_content': b'd'})
    assert res['status'] == 'error'

    res = await m365.execute_onedrive_action('t', 'upload', {'path': 'a'})
    assert res['status'] == 'error'


async def test_onedrive_delete_share_folder(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_onedrive_action(
        't', 'delete', {'item_id': 'i'}))['status'] == 'success'
    assert (await m365.execute_onedrive_action(
        't', 'share', {'item_id': 'i', 'link_type': 'edit'}))['status'] == 'success'
    assert m365._make_graph_request.await_args.args[0] == 'POST'
    assert (await m365.execute_onedrive_action(
        't', 'create_folder', {'name': 'n', 'folder_path': 'd'}))['status'] == 'success'
    assert (await m365.execute_onedrive_action(
        't', 'create_folder', {'name': 'n'}))['status'] == 'success'

    for action, params in (('delete', {}), ('share', {}), ('create_folder', {})):
        res = await m365.execute_onedrive_action('t', action, params)
        assert res['status'] == 'error'

    res = await m365.execute_onedrive_action('t', 'zzz', {})
    assert res['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    res = await m365.execute_onedrive_action(
        't', 'list_files', {})
    assert res == {'status': 'error', 'message': 'OneDrive action failed'}


# ============================================================================
# Microsoft365Service — Excel actions
# ============================================================================

@pytest.fixture()
def xl(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success', 'data': {}})
    return m365


async def test_excel_item_id_resolution(xl):
    # missing both item_id and path
    res = await xl.execute_excel_action('t', 'get_tables', {})
    assert res['status'] == 'error'

    # resolve via path failure
    xl._make_graph_request = AsyncMock(
        return_value={'status': 'error'})
    res = await xl.execute_excel_action('t', 'get_tables', {'path': 'p'})
    assert 'resolve' in res['message']

    # resolve via path success
    xl._make_graph_request = AsyncMock(
        return_value={'status': 'success', 'data': {'id': 'ITEM'}})
    res = await xl.execute_excel_action('t', 'get_tables', {'path': 'p'})
    assert res['status'] == 'success'
    assert 'ITEM' in xl._make_graph_request.await_args.args[1]


async def test_excel_read_write_format(xl):
    assert (await xl.execute_excel_action(
        't', 'read_range', {'item_id': 'i', 'range': 'Sheet1!A1:B2'}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'read_range', {'item_id': 'i', 'range': 'A1:B2'}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'read_range', {'item_id': 'i'}))['status'] == 'error'

    assert (await xl.execute_excel_action(
        't', 'write_range', {'item_id': 'i', 'range': 'S!A1', 'values': [[1]]}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'write_range', {'item_id': 'i', 'range': 'A1'}))['status'] == 'error'

    assert (await xl.execute_excel_action(
        't', 'format_range',
        {'item_id': 'i', 'range': 'S!A1', 'format': {'bold': True}}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'format_range', {'item_id': 'i', 'format': {}}))['status'] == 'error'


async def test_excel_tables_columns(xl):
    assert (await xl.execute_excel_action(
        't', 'get_tables', {'item_id': 'i'}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'get_columns', {'item_id': 'i', 'table': 'T'}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'get_columns', {'item_id': 'i'}))['status'] == 'error'


async def test_excel_append_row(xl):
    assert (await xl.execute_excel_action(
        't', 'append_row', {'item_id': 'i'}))['status'] == 'error'

    # mapping path: columns fetched, values aligned
    xl._make_graph_request = AsyncMock(side_effect=[
        {'status': 'success', 'data': [{'name': 'A'}, {'name': 'B'}]},
        {'status': 'success'},
    ])
    res = await xl.execute_excel_action(
        't', 'append_row',
        {'item_id': 'i', 'table': 'T', 'mapping': {'A': '1', 'B': '2'}})
    assert res['status'] == 'success'

    # mapping path: columns fetch fails
    xl._make_graph_request = AsyncMock(
        return_value={'status': 'error'})
    res = await xl.execute_excel_action(
        't', 'append_row', {'item_id': 'i', 'table': 'T', 'mapping': {'A': '1'}})
    assert res['status'] == 'error'

    # plain values path
    xl._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await xl.execute_excel_action(
        't', 'append_row',
        {'item_id': 'i', 'table': 'T', 'values': ['x']}))['status'] == 'success'


async def test_excel_create_worksheet_unknown_error(xl):
    assert (await xl.execute_excel_action(
        't', 'create_worksheet', {'item_id': 'i', 'name': 'S'}))['status'] == 'success'
    assert (await xl.execute_excel_action(
        't', 'create_worksheet', {'item_id': 'i'}))['status'] == 'error'
    assert (await xl.execute_excel_action(
        't', 'zzz', {'item_id': 'i'}))['status'] == 'error'

    xl._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await xl.execute_excel_action(
        't', 'get_tables', {'item_id': 'i'}))['message'] == 'Excel action failed'


# ============================================================================
# Microsoft365Service — Power BI / Teams / Outlook / Planner
# ============================================================================

async def test_powerbi_actions(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_powerbi_action(
        't', 'refresh_dataset', {'group_id': 'g', 'dataset_id': 'd'}))['status'] == 'success'
    assert (await m365.execute_powerbi_action(
        't', 'get_reports', {'group_id': 'g'}))['status'] == 'success'
    assert (await m365.execute_powerbi_action(
        't', 'get_dashboards', {'group_id': 'g'}))['status'] == 'success'
    assert (await m365.execute_powerbi_action(
        't', 'export_report',
        {'group_id': 'g', 'report_id': 'r', 'format': 'PPTX'}))['status'] == 'success'
    assert (await m365.execute_powerbi_action(
        't', 'get_datasets', {'group_id': 'g'}))['status'] == 'success'

    for action, params in (('refresh_dataset', {'group_id': 'g'}),
                           ('get_reports', {}), ('get_dashboards', {}),
                           ('export_report', {'group_id': 'g'}),
                           ('get_datasets', {}), ('zzz', {})):
        assert (await m365.execute_powerbi_action(
            't', action, params))['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.execute_powerbi_action(
        't', 'get_reports', {'group_id': 'g'}))['message'] == 'Power BI action failed'


async def test_teams_actions(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_teams_action(
        't', 'send_message',
        {'team_id': 'g', 'channel_id': 'c', 'message': 'm'}))['status'] == 'success'
    assert (await m365.execute_teams_action(
        't', 'create_channel',
        {'team_id': 'g', 'display_name': 'n'}))['status'] == 'success'
    assert (await m365.execute_teams_action(
        't', 'list_teams', {}))['status'] == 'success'

    for action, params in (('send_message', {'team_id': 'g'}),
                           ('create_channel', {'team_id': 'g'}),
                           ('zzz', {})):
        assert (await m365.execute_teams_action(
            't', action, params))['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.execute_teams_action(
        't', 'list_teams', {}))['message'] == 'Teams action failed'


async def test_outlook_actions(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_outlook_action(
        't', 'send_email', {'to': 'a@b.c'}))['status'] == 'success'
    assert (await m365.execute_outlook_action(
        't', 'send_email',
        {'to': ['a@b.c'], 'cc': 'x@y.z', 'bcc': ['q@r.s']}))['status'] == 'success'
    assert (await m365.execute_outlook_action(
        't', 'send_email', {}))['status'] == 'error'
    assert (await m365.execute_outlook_action(
        't', 'list_messages', {}))['status'] == 'success'
    assert (await m365.execute_outlook_action(
        't', 'create_event',
        {'start_time': 's', 'end_time': 'e', 'attendees': 'a@b.c'}))['status'] == 'success'
    assert (await m365.execute_outlook_action(
        't', 'create_event', {'body': 'b'}))['status'] == 'error'
    assert (await m365.execute_outlook_action(
        't', 'zzz', {}))['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.execute_outlook_action(
        't', 'list_messages', {}))['message'] == 'Outlook action failed'


async def test_planner_actions(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    assert (await m365.execute_planner_action(
        't', 'create_task',
        {'plan_id': 'p', 'bucket_id': 'b', 'title': 'T', 'description': 'd'}))['status'] == 'success'
    assert (await m365.execute_planner_action(
        't', 'update_task',
        {'task_id': 'x', 'title': 'T', 'description': 'd',
         'percent_complete': 50}))['status'] == 'success'
    assert (await m365.execute_planner_action(
        't', 'list_plans', {'group_id': 'g'}))['status'] == 'success'
    assert (await m365.execute_planner_action(
        't', 'list_buckets', {'plan_id': 'p'}))['status'] == 'success'
    assert (await m365.execute_planner_action(
        't', 'list_tasks', {'plan_id': 'p'}))['status'] == 'success'

    for action, params in (('create_task', {'plan_id': 'p'}),
                           ('update_task', {}), ('list_plans', {}),
                           ('list_buckets', {}), ('list_tasks', {}),
                           ('zzz', {})):
        assert (await m365.execute_planner_action(
            't', action, params))['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.execute_planner_action(
        't', 'list_plans', {'group_id': 'g'}))['message'] == 'Planner action failed'


async def test_delete_item(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    for item_type, item_id, params in (
            ('message', 'm', None), ('event', 'e', None), ('file', 'f', None),
            ('team_message', 'tm', {'team_id': 't', 'channel_id': 'c'})):
        assert (await m365.delete_item(
            'tok', item_type, item_id, params))['status'] == 'success'
    assert (await m365.delete_item(
        'tok', 'team_message', 'tm', {}))['status'] == 'error'
    assert (await m365.delete_item('tok', 'zzz', 'x'))['status'] == 'error'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.delete_item('tok', 'message', 'm'))['status'] == 'error'


async def test_subscriptions(m365):
    m365._make_graph_request = AsyncMock(return_value={'status': 'success'})
    res = await m365.create_subscription(
        't', '/me/messages', 'created,updated', 'https://cb', '2099-01-01')
    assert res['status'] == 'success'
    payload = m365._make_graph_request.await_args.args[3]
    assert 'deleted' in payload['changeType']

    assert (await m365.create_subscription(
        't', '/me/messages', 'updated', 'https://cb', '2099-01-01'))['status'] == 'success'
    assert (await m365.renew_subscription('t', 'sub1', '2099-01-01'))['status'] == 'success'
    assert (await m365.delete_subscription('t', 'sub1'))['status'] == 'success'

    m365._make_graph_request = AsyncMock(side_effect=RuntimeError('x'))
    assert (await m365.create_subscription(
        't', '/r', 'c', 'u', 'e'))['message'] == 'Create subscription failed'
    assert (await m365.renew_subscription('t', 's', 'e'))['message'] == 'Renew subscription failed'
    assert (await m365.delete_subscription('t', 's'))['message'] == 'Delete subscription failed'
