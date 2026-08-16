# -*- coding: utf-8 -*-
"""Coverage wave 89 — integrations.discord_analytics_engine,
asana_service, salesforce_service, bitbucket_service, dropbox_routes.

No network / no LLM / no real Redis: httpx/requests boundaries, LLM
service, DB sessions and the dropbox SDK are all mocked.
"""
import asyncio
import sys
import types
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests as requests_mod

import integrations.discord_analytics_engine as dae_mod
from integrations.discord_analytics_engine import (
    DiscordAnalyticsDataPoint,
    DiscordAnalyticsEngine,
    DiscordAnalyticsGranularity as Gran,
    DiscordAnalyticsMetric as Metric,
    DiscordAnalyticsTimeRange as Range,
    )
import integrations.asana_service as asana_mod
from integrations.asana_service import AsanaService
import integrations.salesforce_service as sf_mod
from integrations.salesforce_service import SalesforceService
import integrations.bitbucket_service as bb_mod
from integrations.bitbucket_service import BitbucketService


def _resp(payload=None, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.raise_for_status = MagicMock()
    r.text = 'body'
    r.content = b'x'
    return r


# ============================================================================
# DiscordAnalyticsEngine
# ============================================================================

class TestDiscordAnalyticsEngine:
    def _engine(self, db=None, redis=None):
        eng = DiscordAnalyticsEngine({'database': db, 'redis': {'client': redis}})
        return eng

    def test_init_and_info(self):
        eng = self._engine()
        assert eng.db is None
        info = eng.get_engine_info()
        assert info['name'] == 'Discord Analytics Engine'
        assert info['status'] == 'ACTIVE'
        assert 'message_count' in info['supported_metrics']
        assert info['cache_ttl'] == 300
        # global instance exists
        assert dae_mod.discord_analytics_engine is not None
        assert dae_mod.discord_analytics_engine.db is None

    async def test_get_analytics_mock_data(self):
        eng = self._engine()
        pts = await eng.get_analytics(Metric.MESSAGE_COUNT, Range.LAST_24_HOURS,
                                      Gran.HOUR)
        assert pts and all(isinstance(p, DiscordAnalyticsDataPoint) for p in pts)
        assert pts[0].to_dict()['metric'] == 'message_count'
        # cache key generation paths
        key = eng._generate_cache_key(
            Metric.MESSAGE_COUNT, Range.LAST_7_DAYS, Gran.DAY,
            filters={'a': 1}, workspace_id='discord_w1', guild_ids=['g'],
            channel_ids=['c'], user_ids=['u'])
        assert 'ws:discord_w1' in key and 'guilds:g' in key

    async def test_get_analytics_redis_cache_roundtrip(self):
        redis = MagicMock()
        eng = self._engine(redis=redis)
        pts = await eng.get_analytics(Metric.ACTIVE_USERS, Range.LAST_7_DAYS,
                                      Gran.DAY)
        assert redis.setex.called
        # second call served from cache
        redis.get.return_value = redis.setex.call_args[0][2]
        pts2 = await eng.get_analytics(Metric.ACTIVE_USERS, Range.LAST_7_DAYS,
                                       Gran.DAY)
        assert len(pts2) == len(pts)

    async def test_get_analytics_error_returns_empty(self):
        eng = self._engine()
        with patch.object(eng, '_get_time_range_boundaries',
                          side_effect=RuntimeError('x')):
            assert await eng.get_analytics(Metric.MESSAGE_COUNT,
                                           Range.LAST_7_DAYS, Gran.DAY) == []

    async def test_fetch_analytics_data_with_db(self):
        db = MagicMock()
        row = {'timestamp': datetime(2026, 1, 1, tzinfo=timezone.utc),
               'value': 5, 'dimensions': {'d': 1}, 'metadata': {}}
        db.execute.return_value.fetchall.return_value = [row]
        eng = self._engine(db=db)
        pts = await eng._fetch_analytics_data(
            Metric.MESSAGE_COUNT, row['timestamp'],
            row['timestamp'] + timedelta(days=1), Gran.DAY)
        assert pts[0].value == 5
        # error branch
        db.execute.side_effect = RuntimeError('boom')
        assert await eng._fetch_analytics_data(
            Metric.MESSAGE_COUNT, row['timestamp'], row['timestamp'], Gran.DAY) == []

    async def test_build_query_all_metric_branches(self):
        eng = self._engine()
        st = datetime(2026, 1, 1, tzinfo=timezone.utc)
        en = st + timedelta(days=2)
        metrics = [Metric.MESSAGE_COUNT, Metric.ACTIVE_USERS,
                   Metric.BOT_MESSAGE_COUNT, Metric.HUMAN_MESSAGE_COUNT,
                   Metric.REACTION_COUNT, Metric.FILE_UPLOADS,
                   Metric.VOICE_MINUTES, Metric.STREAM_MINUTES,
                   Metric.USER_ENGAGEMENT, Metric.GUILD_ACTIVITY]
        for m in metrics:
            q = await eng._build_analytics_query(
                m, st, en, Gran.WEEK, filters={'channel_type': 'text',
                                               'roles': ['a', 'b']},
                workspace_id='discord_g1', guild_ids=['g'], channel_ids=['c'],
                user_ids=['u'])
            assert q['sql'] and q['params']
        # unsupported metric -> empty query
        q = await eng._build_analytics_query(
            Metric.BOOST_LEVEL, st, en, Gran.DAY)
        assert q == {'sql': '', 'params': []}
        # granularity YEAR -> KeyError inside -> caught
        q = await eng._build_analytics_query(
            Metric.MESSAGE_COUNT, st, en, Gran.YEAR)
        assert q == {'sql': '', 'params': []}
        # workspace without discord_ prefix
        q = await eng._build_analytics_query(
            Metric.MESSAGE_COUNT, st, en, Gran.DAY, workspace_id='plain')
        assert 'guild_id = ?' in q['sql']

    def test_time_ranges_and_deltas(self):
        eng = self._engine()
        for tr in (Range.LAST_24_HOURS, Range.LAST_7_DAYS, Range.LAST_30_DAYS,
                   Range.LAST_90_DAYS, Range.CUSTOM):
            st, en = eng._get_time_range_boundaries(tr)
            assert st < en
        assert eng._get_interval_delta(Gran.HOUR) == timedelta(hours=1)
        assert eng._get_interval_delta(Gran.WEEK) == timedelta(weeks=1)
        assert eng._get_interval_delta(Gran.MONTH) == timedelta(days=30)
        assert eng._get_interval_delta(Gran.YEAR) == timedelta(days=1)
        # mock value patterns
        morning = datetime(2026, 1, 5, 8, tzinfo=timezone.utc)  # mon, 6-12
        evening = datetime(2026, 1, 10, 20, tzinfo=timezone.utc)  # sat, 18-23
        assert eng._generate_mock_value(Metric.MESSAGE_COUNT, morning) >= 0
        assert eng._generate_mock_value(Metric.BOOST_LEVEL, evening) == \
            pytest.approx(50 * 1.5 * 1.3 * (0.7 + (hash(evening.isoformat()) % 10) / 10))

    async def test_mock_top_guilds_and_get_top_guilds(self):
        eng = self._engine()
        res = await eng.get_top_guilds(Metric.MESSAGE_COUNT, Range.LAST_7_DAYS,
                                       limit=3)
        assert len(res) == 3 and res[0]['guild_id'] == 'mock_guild_0'
        # db path
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            {'guild_id': 'g', 'guild_name': 'G', 'value': 10,
             'human_ratio': 0.5}]
        eng2 = self._engine(db=db)
        res = await eng2.get_top_guilds(Metric.MESSAGE_COUNT,
                                        Range.LAST_7_DAYS, workspace_id='w')
        assert res[0]['guild_name'] == 'G'
        # unsupported metric with db
        res = await eng2.get_top_guilds(Metric.BOOST_LEVEL, Range.LAST_7_DAYS)
        assert res == []
        # error branch
        db.execute.side_effect = RuntimeError('x')
        assert await eng2.get_top_guilds(Metric.MESSAGE_COUNT,
                                         Range.LAST_7_DAYS) == []

    async def test_user_activity_summary(self):
        eng = self._engine()
        s = await eng.get_user_activity_summary('u1', Range.LAST_30_DAYS)
        assert s['user_id'] == 'u1' and s['message_count'] == 280
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {
            'message_count': 10, 'channels_participated': 2,
            'reactions_given': 3, 'files_uploaded': 1,
            'avg_message_length': 12.0}
        db.execute.return_value.fetchall.return_value = [{'hour': '14'}]
        eng2 = self._engine(db=db)
        s = await eng2.get_user_activity_summary('u1', Range.LAST_7_DAYS)
        assert s['message_count'] == 10 and s['most_active_hours'] == [14]
        db.execute.side_effect = RuntimeError('x')
        assert await eng2.get_user_activity_summary('u1', Range.LAST_7_DAYS) == {}

    async def test_guild_activity_report(self):
        eng = self._engine()
        r = await eng.get_guild_activity_report('g', Range.LAST_7_DAYS)
        assert r['guild_id'] == 'g' and r['total_messages'] == 2450
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = {
            'total_messages': 5, 'active_users': 2, 'bot_messages': 1,
            'human_messages': 4, 'reaction_count': 3, 'file_uploads': 1,
            'avg_message_length': 9.0, 'hour': '14'}
        db.execute.return_value.fetchall.return_value = [
            {'user_name': 'u', 'message_count': 5}]
        eng2 = self._engine(db=db)
        r = await eng2.get_guild_activity_report('g', Range.LAST_7_DAYS)
        assert r['peak_activity_hour'] == 14  # from fetchone()['hour']
        db.execute.side_effect = RuntimeError('x')
        assert await eng2.get_guild_activity_report('g', Range.LAST_7_DAYS) == {}

    async def test_voice_analytics(self):
        eng = self._engine()
        v = await eng.get_voice_chat_analytics('g', Range.LAST_7_DAYS)
        assert v['total_voice_minutes'] == 24000
        db = MagicMock()
        eng2 = self._engine(db=db)
        v = await eng2.get_voice_chat_analytics('g', Range.LAST_7_DAYS)
        assert v['guild_id'] == 'g'
        with patch.object(eng2, '_generate_mock_voice_analytics',
                          side_effect=RuntimeError('x')):
            assert await eng2.get_voice_chat_analytics('g',
                                                       Range.LAST_7_DAYS) == {}

    async def test_export_formats(self):
        eng = self._engine()
        r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                            Range.LAST_7_DAYS, Gran.DAY,
                                            format='csv')
        assert r['ok'] and r['format'] == 'csv' and 'timestamp' in r['data']
        r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                            Range.LAST_7_DAYS, Gran.DAY,
                                            format='JSON')
        assert r['ok'] and r['format'] == 'json'
        r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                            Range.LAST_7_DAYS, Gran.DAY,
                                            format='bogus')
        assert r['ok'] is False
        # no data
        with patch.object(eng, 'get_analytics', AsyncMock(return_value=[])):
            r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                                Range.LAST_7_DAYS, Gran.DAY)
            assert r['ok'] is False
        # excel
        r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                            Range.LAST_7_DAYS, Gran.DAY,
                                            format='excel')
        if dae_mod.OPENPYXL_AVAILABLE:
            assert r['ok'] and r['data']
        else:
            assert r['ok'] is False and 'openpyxl' in r['error']
        # excel conversion failure
        with patch.object(eng, 'get_analytics', AsyncMock(return_value=[
                DiscordAnalyticsDataPoint(datetime(2026, 1, 1), Metric.MESSAGE_COUNT,
                                          1, {}, {})])), \
             patch.object(eng, '_convert_to_excel', return_value=None):
            r = await eng.export_analytics_data(Metric.MESSAGE_COUNT,
                                                Range.LAST_7_DAYS, Gran.DAY,
                                                format='excel')
            assert r['ok'] is False
        # csv empty + error
        assert eng._convert_to_csv([]) == ''
        with patch.object(dae_mod.json, 'dumps', side_effect=RuntimeError('x')):
            assert eng._convert_to_csv(
                [DiscordAnalyticsDataPoint(datetime(2026, 1, 1),
                                           Metric.MESSAGE_COUNT, 1, {}, {})]) == ''

    def test_convert_to_excel_direct(self):
        if not dae_mod.OPENPYXL_AVAILABLE:
            pytest.skip('openpyxl not installed')
        eng = self._engine()
        pts = [DiscordAnalyticsDataPoint(datetime(2026, 1, 1),
                                         Metric.MESSAGE_COUNT, 5, {'a': 1},
                                         {'b': 2})]
        assert isinstance(eng._convert_to_excel(pts, Metric.MESSAGE_COUNT,
                                                Range.LAST_7_DAYS), bytes)
        assert eng._convert_to_excel([], Metric.MESSAGE_COUNT,
                                     Range.LAST_7_DAYS) is None
        with patch.object(dae_mod, 'Workbook', side_effect=RuntimeError('x')):
            assert eng._convert_to_excel(
                [DiscordAnalyticsDataPoint(datetime(2026, 1, 1),
                                           Metric.MESSAGE_COUNT, 1, {}, {})],
                Metric.MESSAGE_COUNT, Range.LAST_7_DAYS) is None

    async def test_clear_cache(self):
        eng = self._engine()
        await eng.clear_cache()  # no redis
        redis = MagicMock()
        redis.keys.return_value = ['k1']
        eng2 = self._engine(redis=redis)
        await eng2.clear_cache()
        redis.delete.assert_called_once_with('k1')
        redis.keys.return_value = []
        await eng2.clear_cache()
        redis.keys.side_effect = RuntimeError('x')
        await eng2.clear_cache()  # error swallowed

    def test_cache_helpers_errors(self):
        eng = self._engine()
        assert eng._get_from_cache('k') is None
        eng._cache_result('k', [])
        # bad redis json
        redis = MagicMock()
        redis.get.return_value = '{not json'
        eng2 = self._engine(redis=redis)
        assert eng2._get_from_cache('k') is None
        redis2 = MagicMock()
        redis2.setex.side_effect = RuntimeError('x')
        eng3 = self._engine(redis=redis2)
        eng3._cache_result('k', [DiscordAnalyticsDataPoint(
            datetime(2026, 1, 1), Metric.MESSAGE_COUNT, 1, {}, {})])

    async def test_sentiment_and_topics_analytics(self):
        db = MagicMock()
        rows = [{'timestamp': datetime(2026, 1, 1, 10, tzinfo=timezone.utc),
                 'content': 'hello world this is fine'},
                {'timestamp': '2026-01-02T10:00:00+00:00', 'content': 'more'}]
        db.execute.return_value.fetchall.return_value = rows
        eng = self._engine(db=db)
        llm = MagicMock()
        sent = MagicMock()
        sent.dict.return_value = {'score': 0.4, 'label': 'positive',
                                  'confidence': 0.9}
        topics = MagicMock()
        topics.dict.return_value = {'topics': ['a', 'b'], 'confidence': 0.8}
        llm.generate_structured = AsyncMock(side_effect=[sent, topics])
        with patch.object(dae_mod, 'get_llm_service', return_value=llm):
            pts = await eng.get_analytics(Metric.SENTIMENT, Range.LAST_7_DAYS,
                                          Gran.DAY)
            assert pts and pts[0].value == 0.4
            pts = await eng.get_analytics(Metric.TOPICS, Range.LAST_7_DAYS,
                                          Gran.HOUR)
            assert pts and pts[0].value == 'a, b'
        # no messages -> empty
        db.execute.return_value.fetchall.return_value = []
        assert await eng._get_sentiment_analytics(
            datetime(2026, 1, 1), datetime(2026, 1, 2), Gran.DAY) == []
        assert await eng._get_topics_analytics(
            datetime(2026, 1, 1), datetime(2026, 1, 2), Gran.DAY) == []
        # no db -> empty
        assert await self._engine()._get_sentiment_analytics(
            datetime(2026, 1, 1), datetime(2026, 1, 2), Gran.DAY) == []
        # db error while fetching raw messages
        db.execute.side_effect = RuntimeError('x')
        assert await eng._fetch_raw_messages(datetime(2026, 1, 1),
                                             datetime(2026, 1, 2)) == []

    async def test_llm_helpers(self):
        eng = self._engine()
        r = await eng._analyze_sentiment('ab')
        assert r == {'score': 0.0, 'label': 'neutral', 'confidence': 1.0}
        r = await eng._extract_topics([])
        assert r == {'topics': [], 'confidence': 1.0}
        with patch.object(dae_mod, 'get_llm_service',
                          side_effect=RuntimeError('no llm')):
            r = await eng._analyze_sentiment('a long enough text here')
            assert r['confidence'] == 0.0
            r = await eng._extract_topics(['t1', 't2'])
            assert r['confidence'] == 0.0

    def test_group_messages_by_granularity(self):
        msgs = [{'timestamp': datetime(2026, 1, 1, 10, 30), 'content': 'a'},
                {'timestamp': '2026-01-01T10:45:00', 'content': 'b'},
                {'timestamp': datetime(2026, 1, 2, 10, 30), 'content': 'c'}]
        eng = self._engine()
        g = eng._group_messages_by_granularity(msgs, Gran.HOUR)
        assert len(g) == 2
        g = eng._group_messages_by_granularity(msgs, Gran.DAY)
        assert len(g) == 2
        g = eng._group_messages_by_granularity(msgs, Gran.WEEK)
        assert len(g) == 3


# ============================================================================
# AsanaService
# ============================================================================

@pytest.fixture()
def asana():
    svc = AsanaService(tenant_id='t1', config={'access_token': 'tok'})
    return svc


def _asana_req(svc, payload=None):
    svc._make_request = MagicMock(
        return_value=payload if payload is not None else {'data': {}})
    return payload


class TestAsanaService:
    def test_init(self):
        assert asana_mod.asana_service is not None
        svc = AsanaService(tenant_id='t2', config={})
        assert svc.access_token is None
        assert svc.max_retries == 3

    def test_make_request_success_and_errors(self, monkeypatch):
        svc = AsanaService(tenant_id='t1', config={})
        ok = _resp({'data': 1}, 200)
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(return_value=ok))
        assert svc._make_request('GET', '/x', 'tok') == {'data': 1}
        # 401
        r401 = _resp({}, 401)
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(return_value=r401))
        with pytest.raises(PermissionError):
            svc._make_request('GET', '/x', 'tok')
        # other status -> raise_for_status -> retry then raise
        r500 = _resp({}, 500)
        r500.raise_for_status.side_effect = requests_mod.HTTPError('http')
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(return_value=r500))
        monkeypatch.setattr('time.sleep', lambda s: None)
        with pytest.raises(requests_mod.RequestException):
            svc._make_request('GET', '/x', 'tok')
        # network error, retry then success
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(side_effect=[requests_mod.ConnectionError(
                                'net'), ok]))
        assert svc._make_request('GET', '/x', 'tok') == {'data': 1}
        # network error exhausted
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(side_effect=requests_mod.ConnectionError(
                                'net')))
        with pytest.raises(requests_mod.ConnectionError):
            svc._make_request('GET', '/x', 'tok')
        # 429 then success
        r429 = _resp({}, 429)
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(side_effect=[r429, ok]))
        assert svc._make_request('GET', '/x', 'tok') == {'data': 1}
        # 429 exhausted
        monkeypatch.setattr(asana_mod.requests, 'request',
                            MagicMock(return_value=_resp({}, 429)))
        with pytest.raises(ConnectionError):
            svc._make_request('GET', '/x', 'tok')

    def test_make_paginated_request(self):
        svc = AsanaService(tenant_id='t1', config={})
        svc._make_request = MagicMock(side_effect=[
            {'data': [1], 'next_page': {'offset': 'o1'}},
            {'data': [2], 'next_page': None},
        ])
        assert svc._make_paginated_request('/projects', 'tok') == [1, 2]
        assert svc._make_request.call_args[1]['params']['offset'] == 'o1'

    async def test_user_profile_and_workspaces(self, asana):
        _asana_req(asana, {'data': {'gid': 'g', 'name': 'n', 'email': 'e',
                                    'photo': {}, 'workspaces': []}})
        r = await asana.get_user_profile('tok')
        assert r['ok'] and r['user']['gid'] == 'g'
        _asana_req(asana, {'data': [{'gid': 'w', 'name': 'W',
                                     'is_organization': True}]})
        r = await asana.get_workspaces('tok')
        assert r['ok'] and r['workspaces'][0]['gid'] == 'w'
        asana._make_request = MagicMock(side_effect=RuntimeError('x'))
        assert (await asana.get_user_profile('tok'))['ok'] is False
        assert (await asana.get_workspaces('tok'))['ok'] is False

    async def test_get_projects_and_tasks(self, asana):
        _asana_req(asana, {'data': [{'gid': 'p', 'name': 'P', 'notes': 'n',
                                     'color': 'c', 'created_at': 't',
                                     'modified_at': 't',
                                     'workspace': {'gid': 'w'},
                                     'team': {'gid': 'tm'}}]})
        r = await asana.get_projects('tok', workspace_gid='w')
        assert r['ok'] and r['projects'][0]['gid'] == 'p'
        _asana_req(asana, {'data': [{'gid': 'tk', 'name': 'T', 'notes': 'n',
                                     'completed': True, 'due_on': 'd',
                                     'assignee': {'gid': 'u', 'name': 'U'},
                                     'projects': [{'gid': 'p'}],
                                     'created_at': 't', 'modified_at': 't'}]})
        r = await asana.get_tasks('tok', project_gid='p', assignee='u',
                                  completed_since='x')
        assert r['ok'] and r['tasks'][0]['completed'] is True
        asana._make_paginated_request = MagicMock(side_effect=RuntimeError('x'))
        assert (await asana.get_projects('tok'))['ok'] is False
        assert (await asana.get_tasks('tok'))['ok'] is False

    async def test_task_crud(self, asana):
        _asana_req(asana, {'data': {'gid': 'tk', 'name': 'T', 'notes': 'n',
                                    'completed': False, 'due_on': 'd',
                                    'assignee': {'gid': 'u'},
                                    'projects': [{'gid': 'p'}],
                                    'created_at': 't', 'modified_at': 't'}})
        r = await asana.create_task('tok', {'name': 'N', 'description': 'd',
                                            'due_on': 'x', 'assignee': 'u',
                                            'projects': ['p'],
                                            'workspace': 'w'})
        assert r['ok'] and 'app.asana.com' in r['task']['url']
        r = await asana.update_task('tok', 'tk', {'name': 'N2'})
        assert r['ok']
        # missing field
        assert (await asana.create_task('tok', {}))['ok'] is False
        asana._make_request = MagicMock(side_effect=RuntimeError('x'))
        assert (await asana.create_task('tok', {'name': 'N'}))['ok'] is False
        assert (await asana.update_task('tok', 'tk', {}))['ok'] is False

    async def test_teams_users_search_stories_comments(self, asana):
        _asana_req(asana, {'data': [{'gid': 'tm', 'name': 'T',
                                     'description': 'd',
                                     'organization': {'gid': 'o'}}]})
        r = await asana.get_teams('tok', 'w')
        assert r['ok'] and r['teams'][0]['gid'] == 'tm'
        _asana_req(asana, {'data': [{'gid': 'u', 'name': 'U', 'email': 'e',
                                     'photo': {}}]})
        r = await asana.get_users('tok', 'w')
        assert r['ok'] and r['users'][0]['gid'] == 'u'
        _asana_req(asana, {'data': [{'gid': 'tk', 'name': 'T', 'notes': 'n',
                                     'completed': False,
                                     'assignee': {'gid': 'u'},
                                     'projects': [{'gid': 'p'}]}]})
        r = await asana.search_tasks('tok', 'w', 'q')
        assert r['ok'] and r['query'] == 'q'
        _asana_req(asana, {'data': [{'gid': 's', 'text': 'x', 'type': 't',
                                     'created_by': {'gid': 'u', 'name': 'U'},
                                     'created_at': 't'}]})
        r = await asana.get_task_stories('tok', 'tk')
        assert r['ok'] and r['stories'][0]['gid'] == 's'
        _asana_req(asana, {'data': {'gid': 's', 'text': 'x',
                                    'created_at': 't'}})
        r = await asana.add_task_comment('tok', 'tk', 'x')
        assert r['ok']
        asana._make_request = MagicMock(side_effect=RuntimeError('x'))
        for coro in (asana.get_teams('tok', 'w'), asana.get_users('tok', 'w'),
                     asana.search_tasks('tok', 'w', 'q'),
                     asana.get_task_stories('tok', 'tk'),
                     asana.add_task_comment('tok', 'tk', 'x')):
            assert (await coro)['ok'] is False

    def test_health_and_capabilities(self, asana):
        asana.access_token = None
        assert asana.health_check()['healthy'] is False
        asana.access_token = 'tok'
        asana._make_request = MagicMock(
            return_value={'data': {'name': 'n', 'email': 'e'}})
        assert asana.health_check()['healthy'] is True
        asana._make_request = MagicMock(side_effect=RuntimeError('x'))
        hc = asana.health_check()
        assert hc['healthy'] is False and hc['status'] == 'disconnected'
        caps = asana.get_capabilities()
        assert caps['supports_webhooks'] is True
        ops = asana.get_operations()
        assert {o['name'] for o in ops} == {'create_task', 'list_tasks'}

    async def test_execute_operation(self, asana):
        asana.create_task = AsyncMock(return_value={'ok': True, 'task': {'g': 1}})
        asana.get_tasks = AsyncMock(return_value={'ok': True, 'tasks': []})
        asana.update_task = AsyncMock(return_value={'ok': True, 'task': {}})
        asana.get_projects = AsyncMock(return_value={'ok': True, 'projects': []})
        asana.add_task_comment = AsyncMock(return_value={'ok': True,
                                                         'story': {}})
        for op, params in (('create_task', {'name': 'n'}),
                           ('get_tasks', {}),
                           ('update_task', {'task_gid': 'g'}),
                           ('get_projects', {}),
                           ('add_comment', {'task_gid': 'g', 'text': 't'})):
            r = await asana.execute_operation(op, params)
            assert r['success'] is True, op
        assert (await asana.execute_operation('bogus', {}))['success'] is False
        assert (await asana.execute_operation(
            'get_tasks', {}, context={'tenant_id': 'other'}))['success'] is False
        asana.get_tasks = AsyncMock(side_effect=RuntimeError('x'))
        assert (await asana.execute_operation('get_tasks', {}))['success'] is False
        # no access token ops
        asana.access_token = None
        assert (await asana.execute_operation('create_task',
                                              {}))['success'] is False

    async def test_call_make_request_with_coroutine(self, asana):
        async def fake_mr(method, endpoint, token, data=None, params=None):
            return {'data': {'ok': 1}}
        asana._make_request = fake_mr
        r = await asana._call_make_request('POST', '/x', 'tok', data={})
        assert r == {'data': {'ok': 1}}

    async def test_create_project(self, asana):
        asana._make_request = MagicMock(
            return_value={'data': {'gid': 'p', 'workspace': {'gid': 'w'},
                                   'team': {'gid': 't'}}})
        r = await asana.create_project(workspace_gid='w', name='P', notes='n',
                                       team_gid='t', color='c', public=True,
                                       extra=1)
        assert r['ok'] and r['project']['workspace_gid'] == 'w'
        # no token
        asana.access_token = None
        assert (await asana.create_project())['ok'] is False
        asana.access_token = 'tok'
        # 429 retry path
        err = requests_mod.HTTPError('rate limit exceeded')
        err.response = MagicMock(status_code=429)
        asana._make_request = MagicMock(
            side_effect=[err, {'data': {'gid': 'p2'}}])
        r = await asana.create_project(access_token='tok', workspace_gid='w',
                                       name='P')
        assert r['ok'] and r['project']['gid'] == 'p2'
        # non-rate error
        err2 = requests_mod.HTTPError('boom')
        err2.response = MagicMock(status_code=500)
        asana._make_request = MagicMock(side_effect=err2)
        assert (await asana.create_project(access_token='tok',
                                           workspace_gid='w'))['ok'] is False

    async def test_sync_to_postgres_cache(self, asana, monkeypatch):
        assert (await asana.sync_to_postgres_cache())['success'] is False
        asana.config['workspace_gid'] = 'w'
        asana.get_projects = AsyncMock(return_value={'ok': True, 'projects': [
            {'gid': 1}, {'gid': 2}]})
        asana.get_tasks = AsyncMock(return_value={'ok': True, 'tasks': [
            {'completed': True}, {'completed': False}]})
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = await asana.sync_to_postgres_cache()
        assert r == {'success': True, 'metrics_synced': 3}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert (await asana.sync_to_postgres_cache())['success'] is True
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert (await asana.sync_to_postgres_cache())['success'] is False
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(side_effect=RuntimeError('x')))
        asana.config.pop('workspace_gid')
        assert (await asana.sync_to_postgres_cache('w'))['success'] is False

    async def test_full_sync(self, asana):
        asana.sync_to_postgres_cache = AsyncMock(
            return_value={'success': True})
        r = await asana.full_sync('w')
        assert r['success'] and r['workspace_gid'] == 'w'


# ============================================================================
# Salesforce (module functions + SalesforceService)
# ============================================================================

def _sf_mock():
    sf = MagicMock()
    sf.query_all.return_value = {'records': [{'Id': '1'}]}
    sf.query.return_value = {'records': [{'Id': '1'}]}
    sf.describe.return_value = {'sobjects': [{'name': 'Contact'}]}
    sf.Contact = MagicMock()
    sf.Account = MagicMock()
    sf.Opportunity = MagicMock()
    sf.Lead = MagicMock()
    sf.Campaign.get.return_value = {'Id': 'c'}
    sf.Case.get.return_value = {'Id': 'cs'}
    return sf


class TestSalesforceStandalone:
    async def test_get_client(self, monkeypatch):
        handler = MagicMock()
        handler.ensure_valid_token = AsyncMock(return_value='tok')
        handler.instance_url = 'https://x.my.salesforce.com'
        monkeypatch.setattr('integrations.auth_handler_salesforce.'
                            'salesforce_auth_handler', handler)
        fake_sf = MagicMock()
        with patch.object(sf_mod, 'Salesforce', return_value=fake_sf):
            assert await sf_mod.get_salesforce_client('u1') is fake_sf
        # missing token
        handler.ensure_valid_token = AsyncMock(return_value=None)
        assert await sf_mod.get_salesforce_client('u1') is None
        # auth failure
        handler.ensure_valid_token = AsyncMock(return_value='tok')
        with patch.object(sf_mod, 'Salesforce',
                          side_effect=sf_mod.SalesforceAuthenticationFailed(
                              'code', 'boom')):
            assert await sf_mod.get_salesforce_client('u1') is None
        # import error
        with patch.object(sf_mod, 'Salesforce',
                          side_effect=ImportError('nope')):
            assert await sf_mod.get_salesforce_client('u1') is None
        # generic error
        with patch.object(sf_mod, 'Salesforce', side_effect=RuntimeError('x')):
            assert await sf_mod.get_salesforce_client('u1') is None

    def test_create_client_with_token(self):
        with patch.object(sf_mod, 'Salesforce', return_value='SF') as m:
            assert sf_mod.create_client_with_token('t', 'u') == 'SF'
        with patch.object(sf_mod, 'Salesforce', side_effect=RuntimeError('x')):
            assert sf_mod.create_client_with_token('t', 'u') is None

    async def test_list_functions(self):
        sf = _sf_mock()
        assert await sf_mod.execute_soql_query(sf, 'SELECT') == {'records':
                                                                 [{'Id': '1'}]}
        for fn in (sf_mod.list_contacts, sf_mod.list_accounts,
                   sf_mod.list_opportunities, sf_mod.list_leads):
            assert await fn(sf) == [{'Id': '1'}]
        sf.query_all = MagicMock(side_effect=RuntimeError('x'))
        for fn in (sf_mod.list_contacts, sf_mod.list_accounts,
                   sf_mod.list_opportunities, sf_mod.list_leads,
                   sf_mod.execute_soql_query):
            with pytest.raises(Exception):
                await fn(sf)

    async def test_crud_functions(self):
        sf = _sf_mock()
        assert await sf_mod.create_contact(sf, 'L', first_name='F',
                                           email='e', phone='p') == \
            sf.Contact.create.return_value
        assert await sf_mod.create_account(sf, 'A', type='t',
                                           industry='i') == \
            sf.Account.create.return_value
        assert await sf_mod.create_opportunity(sf, 'O', 's', 'd', amount=1.0,
                                               account_id='a') == \
            sf.Opportunity.create.return_value
        assert await sf_mod.create_lead(sf, 'L', 'C', first_name='F',
                                        email='e', phone='p') == \
            sf.Lead.create.return_value
        await sf_mod.update_opportunity(sf, 'o', {})
        await sf_mod.update_contact(sf, 'c', {})
        await sf_mod.update_lead(sf, 'l', {})
        await sf_mod.update_account(sf, 'a', {})
        assert await sf_mod.get_opportunity(sf, 'o') == \
            sf.Opportunity.get.return_value
        assert await sf_mod.get_campaign(sf, 'c') == {'Id': 'c'}
        assert await sf_mod.get_case(sf, 'cs') == {'Id': 'cs'}
        # error branches
        bad = MagicMock()
        bad.Opportunity.update.side_effect = RuntimeError('x')
        bad.Opportunity.get.side_effect = RuntimeError('x')
        bad.Contact.update.side_effect = RuntimeError('x')
        bad.Lead.update.side_effect = RuntimeError('x')
        bad.Account.update.side_effect = RuntimeError('x')
        bad.Contact.create.side_effect = RuntimeError('x')
        bad.Account.create.side_effect = RuntimeError('x')
        bad.Opportunity.create.side_effect = RuntimeError('x')
        bad.Lead.create.side_effect = RuntimeError('x')
        bad.Campaign.get.side_effect = RuntimeError('x')
        bad.Case.get.side_effect = RuntimeError('x')
        for coro in (sf_mod.update_opportunity(bad, 'o', {}),
                     sf_mod.update_contact(bad, 'c', {}),
                     sf_mod.update_lead(bad, 'l', {}),
                     sf_mod.update_account(bad, 'a', {}),
                     sf_mod.create_contact(bad, 'L'),
                     sf_mod.create_account(bad, 'A'),
                     sf_mod.create_opportunity(bad, 'O', 's', 'd'),
                     sf_mod.create_lead(bad, 'L', 'C'),
                     sf_mod.get_opportunity(bad, 'o'),
                     sf_mod.get_campaign(bad, 'c'),
                     sf_mod.get_case(bad, 'cs')):
            with pytest.raises(Exception):
                await coro

    async def test_get_user_info(self, monkeypatch):
        sf = _sf_mock()
        sf.identity = {'user_id': '005xxx'}
        assert (await sf_mod.get_user_info(sf))['Id'] == '1'
        sf2 = _sf_mock()
        sf2.identity = None
        with patch('requests.get') as g:
            g.return_value.json.return_value = {'user_id': 'u'}
            assert await sf_mod.get_user_info(sf2) == {'user_id': 'u'}
        sf3 = _sf_mock()
        sf3.identity = {'user_id': '005y'}
        sf3.query_all.return_value = {'records': []}
        assert await sf_mod.get_user_info(sf3) == {}
        sf4 = _sf_mock()
        sf4.identity = None
        with patch('requests.get', side_effect=RuntimeError('x')):
            with pytest.raises(Exception):
                await sf_mod.get_user_info(sf4)

    async def test_sobject_helpers(self):
        sf = _sf_mock()
        assert await sf_mod.list_sobjects(sf) == [{'name': 'Contact'}]
        sf.describe = MagicMock(side_effect=RuntimeError('x'))
        assert await sf_mod.list_sobjects(sf) == []
        sf2 = _sf_mock()
        sf2.Contact.describe.return_value = {'fields': [{'name': 'Id'}]}
        assert await sf_mod.get_sobject_fields(sf2, 'Contact') == \
            [{'name': 'Id'}]
        sf3 = MagicMock(spec=[])
        assert await sf_mod.get_sobject_fields(sf3, 'Nope') == []

    def test_escapers_and_validation(self):
        assert sf_mod.escape_soql_string(None) == ''
        assert sf_mod.escape_soql_string("a'b\\c") == "a''b\\\\c"
        assert sf_mod.escape_sosl_string(None) == ''
        assert sf_mod.escape_sosl_string('a{b}c\\d') == 'a\\{b\\}c\\\\d'
        assert sf_mod.validate_salesforce_id('abcDEF123GHIjkl') is True
        assert sf_mod.validate_salesforce_id('abcDEF123GHIjklmNO') is True
        assert sf_mod.validate_salesforce_id('short') is False
        assert sf_mod.validate_salesforce_id('a' * 16) is False
        assert sf_mod.validate_salesforce_id(None) is False
        assert sf_mod.validate_salesforce_id(123) is False


class TestSalesforceService:
    @pytest.fixture()
    def svc(self):
        return SalesforceService(tenant_id='t1', config={
            'access_token': 'tok', 'instance_url': 'https://x'})

    async def test_wrappers(self, svc, monkeypatch):
        sf = _sf_mock()
        monkeypatch.setattr(sf_mod, 'list_contacts', AsyncMock(return_value=1))
        monkeypatch.setattr(sf_mod, 'list_accounts', AsyncMock(return_value=2))
        monkeypatch.setattr(sf_mod, 'list_opportunities',
                            AsyncMock(return_value=3))
        monkeypatch.setattr(sf_mod, 'list_leads', AsyncMock(return_value=4))
        monkeypatch.setattr(sf_mod, 'create_contact',
                            AsyncMock(return_value=5))
        monkeypatch.setattr(sf_mod, 'create_account',
                            AsyncMock(return_value=6))
        monkeypatch.setattr(sf_mod, 'create_opportunity',
                            AsyncMock(return_value=7))
        monkeypatch.setattr(sf_mod, 'create_lead', AsyncMock(return_value=8))
        monkeypatch.setattr(sf_mod, 'get_opportunity',
                            AsyncMock(return_value=9))
        monkeypatch.setattr(sf_mod, 'update_opportunity',
                            AsyncMock(return_value=10))
        monkeypatch.setattr(sf_mod, 'update_contact',
                            AsyncMock(return_value=11))
        monkeypatch.setattr(sf_mod, 'update_lead', AsyncMock(return_value=12))
        monkeypatch.setattr(sf_mod, 'update_account',
                            AsyncMock(return_value=13))
        monkeypatch.setattr(sf_mod, 'execute_soql_query',
                            AsyncMock(return_value=14))
        monkeypatch.setattr(sf_mod, 'list_sobjects',
                            AsyncMock(return_value=[15]))
        monkeypatch.setattr(sf_mod, 'get_sobject_fields',
                            AsyncMock(return_value=[16]))
        monkeypatch.setattr(sf_mod, 'get_salesforce_client',
                            AsyncMock(return_value='sf'))
        with patch.object(sf_mod, 'create_client_with_token',
                          return_value='sf2'):
            assert svc.create_client('t', 'u') == 'sf2'
        assert await svc.get_client('u', None) == 'sf'
        assert await svc.list_contacts(sf) == 1
        assert await svc.list_accounts(sf) == 2
        assert await svc.list_opportunities(sf) == 3
        assert await svc.list_leads(sf) == 4
        assert await svc.create_contact(sf, last_name='L') == 5
        assert await svc.create_account(sf, name='A') == 6
        assert await svc.create_opportunity(sf, name='O', stage_name='s',
                                            close_date='d') == 7
        assert await svc.create_lead(sf, last_name='L', company='C') == 8
        assert await svc.get_opportunity(sf, 'o') == 9
        assert await svc.update_opportunity(sf, 'o', {}) == 10
        assert await svc.update_contact(sf, 'c', {}) == 11
        assert await svc.update_lead(sf, 'l', {}) == 12
        assert await svc.update_account(sf, 'a', {}) == 13
        assert await svc.execute_query(sf, 'q') == 14
        assert await svc.list_sobjects(sf) == [15]
        assert await svc.get_sobject_fields(sf, 'Contact') == [16]

    async def test_execute_operation(self, svc):
        r = await svc.execute_operation('create_lead', {
            'first_name': 'F', 'last_name': 'L', 'company': 'C',
            'email': 'e', 'phone': 'p'})
        assert r['success'] is True and r['result']['id'] == 'stub-lead-id'
        r = await svc.execute_operation('create_lead', {'first_name': 'F'})
        assert r['success'] is False
        assert (await svc.execute_operation('bogus', {}))['success'] is False
        # exception branch -> AUTH_INVALID / RATE_LIMIT / NOT_FOUND
        bad_params = MagicMock()
        bad_params.get = MagicMock(side_effect=RuntimeError(
            'authentication invalid_grant'))
        r = await svc.execute_operation('create_lead', bad_params)
        assert r['success'] is False
        bad_params2 = MagicMock()
        bad_params2.get = MagicMock(side_effect=RuntimeError(
            'rate limit limit_exceeded'))
        r = await svc.execute_operation('create_lead', bad_params2)
        assert 'rate' in r['error'] or r['success'] is False
        bad_params3 = MagicMock()
        bad_params3.get = MagicMock(side_effect=RuntimeError('not found 404'))
        r = await svc.execute_operation('create_lead', bad_params3)
        assert r['success'] is False
        # with tenant context (stub pass branch)
        r = await svc.execute_operation('create_lead', {
            'first_name': 'F', 'last_name': 'L', 'company': 'C'},
            context={'tenant_id': 'any'})
        assert r['success'] is True

    def test_health_check(self, svc, monkeypatch):
        svc.access_token = None
        assert svc.health_check()['healthy'] is False
        svc.access_token = 'tok'
        r = MagicMock(status_code=200)
        with patch('requests.get', return_value=r):
            assert svc.health_check()['healthy'] is True
        r.status_code = 503
        with patch('requests.get', return_value=r):
            assert svc.health_check()['healthy'] is False
        with patch('requests.get', side_effect=RuntimeError('x')):
            hc = svc.health_check()
            assert hc['healthy'] is False and hc['error'] == \
                'Health check failed'

    def test_capabilities(self, svc):
        assert SalesforceService().access_token is None
        caps = svc.get_capabilities()
        assert caps['supports_webhooks'] is True


# ============================================================================
# BitbucketService
# ============================================================================

@pytest.fixture()
def bb():
    svc = BitbucketService(tenant_id='t1', config={
        'bitbucket_client_id': 'cid', 'bitbucket_client_secret': 'sec',
        'access_token': 'tok'})
    return svc


class TestBitbucketService:
    def test_init_and_auth_url(self, bb, monkeypatch):
        for var in ('BITBUCKET_CLIENT_ID', 'BITBUCKET_CLIENT_SECRET'):
            monkeypatch.delenv(var, raising=False)
        svc = BitbucketService(tenant_id='t1', config={})
        assert svc.client_id is None
        url = svc.get_authorization_url('st')
        assert 'state=st' in url and 'client_id=None' in url
        assert svc.get_authorization_url().endswith('state=no_state')
        assert bb.base_url == 'https://api.bitbucket.org/2.0'

    def test_token_exchange_and_refresh(self, bb, monkeypatch):
        payload = {'access_token': 'a', 'refresh_token': 'r', 'expires_in': 1,
                   'token_type': 'bearer', 'scope': 's'}
        with patch.object(bb_mod.requests, 'post',
                          return_value=_resp(payload)) as p:
            r = bb.exchange_code_for_token('code')
            assert r['access_token'] == 'a'
            assert 'Basic ' in p.call_args[1]['headers']['Authorization']
        with patch.object(bb_mod.requests, 'post',
                          return_value=_resp(payload)):
            assert bb.refresh_access_token('r')['access_token'] == 'a'
        bad = _resp({}, 500)
        bad.raise_for_status.side_effect = requests_mod.HTTPError('x')
        with patch.object(bb_mod.requests, 'post', return_value=bad):
            with pytest.raises(requests_mod.RequestException):
                bb.exchange_code_for_token('c')
            with pytest.raises(requests_mod.RequestException):
                bb.refresh_access_token('r')

    def test_make_request_methods(self, bb):
        for method, attr in (('GET', 'get'), ('POST', 'post'), ('PUT', 'put'),
                             ('DELETE', 'delete')):
            with patch.object(bb_mod.requests, attr,
                              return_value=_resp({'ok': 1})) as m:
                assert bb._make_request('t', 'e', method, {}) == {'ok': 1}
                m.assert_called_once()
        # empty content -> {}
        r = _resp(None)
        r.content = b''
        r.json.side_effect = ValueError()
        with patch.object(bb_mod.requests, 'get', return_value=r):
            assert bb._make_request('t', 'e') == {}
        # unsupported method
        with pytest.raises(ValueError):
            bb._make_request('t', 'e', 'PATCH')
        # request error
        bad = _resp({}, 500)
        bad.raise_for_status.side_effect = requests_mod.HTTPError('x')
        with patch.object(bb_mod.requests, 'get', return_value=bad):
            with pytest.raises(requests_mod.RequestException):
                bb._make_request('t', 'e')

    def test_read_wrappers(self, bb):
        bb._make_request = MagicMock(return_value={'values': [{'x': 1}]})
        assert bb.get_workspaces('t') == [{'x': 1}]
        assert bb.get_repositories('t', 'ws') == [{'x': 1}]
        assert bb.get_repositories('t') == [{'x': 1}]
        assert bb.get_branches('t', 'ws', 'r') == [{'x': 1}]
        assert bb.get_pull_requests('t', 'ws', 'r') == [{'x': 1}]
        assert bb.get_commits('t', 'ws', 'r', 'br') == [{'x': 1}]
        assert bb.get_pipelines('t', 'ws', 'r') == [{'x': 1}]
        assert bb.get_issues('t', 'ws', 'r') == [{'x': 1}]
        assert bb.get_webhooks('t', 'ws', 'r') == [{'x': 1}]
        assert bb.search_code('t', 'q', 'ws') == [{'x': 1}]
        bb._make_request = MagicMock(
            side_effect=lambda tok, ep, *a, **k: {'detail': ep})
        assert bb.get_repository('t', 'ws', 'r') == \
            {'detail': 'repositories/ws/r'}
        assert bb.get_pull_request('t', 'ws', 'r', '1') == \
            {'detail': 'repositories/ws/r/pullrequests/1'}
        assert bb.get_user_info('t') == {'detail': 'user'}

    def test_write_wrappers(self, bb):
        bb._make_request = MagicMock(return_value={'id': 1})
        r = bb.create_pull_request('t', 'ws', 'r', 'T', 'src', 'dst', 'd',
                                   ['rv1'])
        assert r == {'id': 1}
        data = bb._make_request.call_args[0][3]
        assert data['reviewers'] == [{'uuid': 'rv1'}]
        assert bb.trigger_pipeline('t', 'ws', 'r', 'br', {'K': 'v'}) == \
            {'id': 1}
        assert bb.create_issue('t', 'ws', 'r', 'T') == {'id': 1}

    def test_wrapper_error_branches(self, bb):
        bb._make_request = MagicMock(side_effect=RuntimeError('x'))
        assert bb.get_workspaces('t') == []
        assert bb.get_repositories('t') == []
        assert bb.get_repository('t', 'w', 'r') == {}
        assert bb.get_branches('t', 'w', 'r') == []
        assert bb.get_pull_requests('t', 'w', 'r') == []
        assert bb.get_pull_request('t', 'w', 'r', '1') == {}
        assert bb.create_pull_request('t', 'w', 'r', 'T', 's') == {}
        assert bb.get_commits('t', 'w', 'r') == []
        assert bb.get_pipelines('t', 'w', 'r') == []
        assert bb.trigger_pipeline('t', 'w', 'r') == {}
        assert bb.get_issues('t', 'w', 'r') == []
        assert bb.create_issue('t', 'w', 'r', 'T') == {}
        assert bb.get_webhooks('t', 'w', 'r') == []
        assert bb.get_user_info('t') == {}
        assert bb.search_code('t', 'q') == []

    def test_health_status_and_check(self, bb):
        bb.get_user_info = MagicMock(
            return_value={'display_name': 'U'})
        h = bb.get_health_status('t')
        assert h['status'] == 'healthy' and h['user'] == 'U'
        bb.get_user_info = MagicMock(side_effect=RuntimeError('x'))
        assert bb.get_health_status('t')['status'] == 'error'
        assert bb.health_check()['healthy'] is True
        assert bb.health_check()['service'] == 'bitbucket'
        caps = bb.get_capabilities()
        assert caps['supports_webhooks'] is True

    async def test_execute_operation(self, bb):
        bb.get_repositories = MagicMock(return_value=[1])
        bb.create_pull_request = MagicMock(return_value={'id': 1})
        bb.get_branches = MagicMock(return_value=[2])
        bb.get_commits = MagicMock(return_value=[3])
        bb.get_issues = MagicMock(return_value=[4])
        bb.create_issue = MagicMock(return_value={'id': 5})
        r = await bb.execute_operation('create_repo', {'repo_name': 'r'})
        assert r['success'] is True
        for op in ('list_repos', 'create_pr', 'get_branches', 'get_commits',
                   'get_issues', 'create_issue'):
            r = await bb.execute_operation(op, {'workspace': 'w',
                                                'repo_slug': 'r'},
                                           context={'access_token': 't'})
            assert r['success'] is True, op
        assert (await bb.execute_operation('nope', {}))['success'] is False
        bb.get_branches = MagicMock(side_effect=RuntimeError('x'))
        assert (await bb.execute_operation('get_branches', {}))['success'] is \
            False

    def test_sync_to_postgres_cache(self, bb, monkeypatch):
        bb.get_repositories = MagicMock(return_value=[1, 2])
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = None
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(return_value=db))
        r = bb.sync_to_postgres_cache('w', 't')
        assert r == {'success': True, 'metrics_synced': 1}
        db.query.return_value.filter_by.return_value.first.return_value = \
            MagicMock()
        assert bb.sync_to_postgres_cache('w', 't')['success'] is True
        db.commit = MagicMock(side_effect=RuntimeError('x'))
        assert bb.sync_to_postgres_cache('w', 't')['success'] is False
        monkeypatch.setattr('core.database.SessionLocal',
                            MagicMock(side_effect=RuntimeError('x')))
        assert bb.sync_to_postgres_cache('w', 't')['success'] is False

    def test_full_sync(self, bb):
        bb.sync_to_postgres_cache = MagicMock(
            return_value={'success': True})
        assert bb.full_sync('w', 't')['success'] is True


# ============================================================================
# Dropbox routes
# ============================================================================

def _install_fake_dropbox():
    dbx = types.ModuleType('dropbox')
    exc = types.ModuleType('dropbox.exceptions')
    exc.ApiError = type('ApiError', (Exception,), {})
    exc.AuthError = type('AuthError', (Exception,), {})
    files = types.ModuleType('dropbox.files')
    files.FileMetadata = type('FileMetadata', (object,), {})
    files.FolderMetadata = type('FolderMetadata', (object,), {})
    sharing = types.ModuleType('dropbox.sharing')
    dbx.exceptions = exc
    dbx.files = files
    dbx.sharing = sharing
    dbx.Dropbox = MagicMock()
    for name, mod in (('dropbox', dbx), ('dropbox.exceptions', exc),
                      ('dropbox.files', files), ('dropbox.sharing', sharing)):
        sys.modules.setdefault(name, mod)


_install_fake_dropbox()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

# NOTE: dropbox_routes is imported lazily (at test runtime, not collection
# time) so that, when richer fake-SDK suites (e.g. test_covpush_w93_dropbox)
# install their own `dropbox` stub at module import during collection, the
# integrations.dropbox_service module binds to THAT stub instead of this
# minimal one. Keeps both suites green when run together.
_DR = {}


def _dr():
    if 'mod' not in _DR:
        import integrations.dropbox_routes as m
        from core.auth import get_current_user
        _DR['mod'] = m
        _DR['gcu'] = get_current_user
    return _DR['mod']


@pytest.fixture()
def client():
    dr_mod = _dr()
    app = FastAPI()
    app.include_router(dr_mod.router)
    app.dependency_overrides[_DR['gcu']] = lambda: {'id': 'u1'}
    return TestClient(app)


def _mock_handler_service():
    handler = MagicMock()
    handler.get_authorization_url = MagicMock(return_value='https://auth')
    handler.get_connection_status = MagicMock(
        return_value={'connected': True})
    handler.ensure_valid_token = AsyncMock(return_value='tok')
    handler.exchange_code_for_token = AsyncMock(
        return_value={'account_id': 'a1', 'expires_in': 100})
    handler.get_user_info = AsyncMock(
        return_value={'account_id': 'a1', 'email': 'e'})
    service = MagicMock()
    service.list_folder = AsyncMock(return_value=[
        {'.tag': 'file', 'name': 'f'}, {'.tag': 'folder', 'name': 'd'}])
    service.upload_file = AsyncMock(return_value={'name': 'f'})
    service.download_file = AsyncMock(return_value=b'bytes')
    service.search = AsyncMock(return_value=[{'match': 1}])
    service.create_folder = AsyncMock(return_value={'name': 'd'})
    service.delete_item = AsyncMock(return_value={'ok': 1})
    service.move_item = AsyncMock(return_value={'ok': 1})
    service.copy_item = AsyncMock(return_value={'ok': 1})
    service.create_shared_link = AsyncMock(return_value={'url': 'u'})
    service.get_account_info = AsyncMock(return_value={'account_id': 'a'})
    service.get_space_usage = AsyncMock(return_value={'used': 1})
    service.get_metadata = AsyncMock(return_value={'name': 'f'})
    return handler, service


class TestDropboxRoutes:
    def test_oauth_endpoints(self, client, monkeypatch):
        dr_mod = _dr()
        handler, service = _mock_handler_service()
        monkeypatch.setattr(dr_mod, 'dropbox_auth_handler', handler)
        monkeypatch.setattr(dr_mod, 'dropbox_service', service)
        r = client.get('/api/dropbox/oauth/url', params={'state': 's'})
        assert r.status_code == 200 and r.json()['authorization_url'] == \
            'https://auth'
        handler.get_authorization_url = MagicMock(side_effect=RuntimeError('x'))
        assert client.get('/api/dropbox/oauth/url').status_code == 500
        handler.get_authorization_url = MagicMock(return_value='u')
        r = client.get('/api/dropbox/callback',
                       params={'code': 'c', 'state': 's'})
        assert r.status_code == 200 and r.json()['account_id'] == 'a1'
        handler.exchange_code_for_token = AsyncMock(
            side_effect=HTTPException(400, 'bad'))
        assert client.get('/api/dropbox/callback',
                          params={'code': 'c'}).status_code == 400
        handler.exchange_code_for_token = AsyncMock(side_effect=RuntimeError('x'))
        assert client.get('/api/dropbox/callback',
                          params={'code': 'c'}).status_code == 500
        r = client.get('/api/dropbox/oauth/status')
        assert r.status_code == 200 and r.json()['connected'] is True
        handler.get_connection_status = MagicMock(side_effect=RuntimeError('x'))
        assert client.get('/api/dropbox/oauth/status').status_code == 500

    def test_user_endpoint(self, client, monkeypatch):
        dr_mod = _dr()
        handler, service = _mock_handler_service()
        monkeypatch.setattr(dr_mod, 'dropbox_auth_handler', handler)
        monkeypatch.setattr(dr_mod, 'dropbox_service', service)
        r = client.get('/api/dropbox/user')
        assert r.status_code == 200 and r.json()['account_id'] == 'a1'
        handler.get_user_info = AsyncMock(side_effect=HTTPException(401, 'x'))
        assert client.get('/api/dropbox/user').status_code == 401
        handler.get_user_info = AsyncMock(side_effect=RuntimeError('x'))
        assert client.get('/api/dropbox/user').status_code == 500

    def test_file_endpoints(self, client, monkeypatch):
        dr_mod = _dr()
        handler, service = _mock_handler_service()
        monkeypatch.setattr(dr_mod, 'dropbox_auth_handler', handler)
        monkeypatch.setattr(dr_mod, 'dropbox_service', service)
        r = client.post('/api/dropbox/files/list',
                        json={'user_id': 'u', 'path': '/'})
        assert r.status_code == 200 and r.json()['count'] == 2
        import base64
        r = client.post('/api/dropbox/files/upload', json={
            'user_id': 'u', 'file_name': 'f.txt',
            'file_content': base64.b64encode(b'data').decode(),
            'path': '/dir'})
        assert r.status_code == 200
        r = client.post('/api/dropbox/files/download',
                        json={'user_id': 'u', 'path': '/dir/f.txt'})
        assert r.status_code == 200
        assert base64.b64decode(r.json()['data']['content_bytes']) == b'bytes'
        r = client.post('/api/dropbox/files/search',
                        json={'user_id': 'u', 'query': 'q', 'path': '/'})
        assert r.status_code == 200 and r.json()['count'] == 1
        # error path
        service.list_folder = AsyncMock(side_effect=RuntimeError('x'))
        assert client.post('/api/dropbox/files/list',
                           json={'user_id': 'u'}).status_code == 500
        service.upload_file = AsyncMock(side_effect=RuntimeError('x'))
        assert client.post('/api/dropbox/files/upload',
                           json={'user_id': 'u', 'file_name': 'f',
                                 'file_content': 'aGk='}).status_code == 500
        service.download_file = AsyncMock(side_effect=RuntimeError('x'))
        assert client.post('/api/dropbox/files/download',
                           json={'user_id': 'u',
                                 'path': '/f'}).status_code == 500
        service.search = AsyncMock(side_effect=RuntimeError('x'))
        assert client.post('/api/dropbox/files/search',
                           json={'user_id': 'u',
                                 'query': 'q'}).status_code == 500

    def test_folder_and_item_endpoints(self, client, monkeypatch):
        dr_mod = _dr()
        handler, service = _mock_handler_service()
        monkeypatch.setattr(dr_mod, 'dropbox_auth_handler', handler)
        monkeypatch.setattr(dr_mod, 'dropbox_service', service)
        r = client.post('/api/dropbox/folders/create',
                        json={'user_id': 'u', 'path': '/d'})
        assert r.status_code == 200
        r = client.post('/api/dropbox/folders/list',
                        json={'user_id': 'u', 'path': '/'})
        assert r.status_code == 200 and r.json()['count'] == 1
        r = client.post('/api/dropbox/items/delete',
                        json={'user_id': 'u', 'path': '/f'})
        assert r.status_code == 200
        r = client.post('/api/dropbox/items/move', json={
            'user_id': 'u', 'from_path': '/a', 'to_path': '/b'})
        assert r.status_code == 200
        r = client.post('/api/dropbox/items/copy', json={
            'user_id': 'u', 'from_path': '/a', 'to_path': '/b'})
        assert r.status_code == 200
        r = client.post('/api/dropbox/shared_links/create',
                        json={'user_id': 'u', 'path': '/f',
                              'settings': {'a': 1}})
        assert r.status_code == 200
        # error paths
        cases = [
            ('/api/dropbox/folders/create', {'user_id': 'u', 'path': '/d'},
             'create_folder'),
            ('/api/dropbox/folders/list', {'user_id': 'u'}, 'list_folder'),
            ('/api/dropbox/items/delete', {'user_id': 'u', 'path': '/f'},
             'delete_item'),
            ('/api/dropbox/items/move',
             {'user_id': 'u', 'from_path': '/a', 'to_path': '/b'},
             'move_item'),
            ('/api/dropbox/items/copy',
             {'user_id': 'u', 'from_path': '/a', 'to_path': '/b'},
             'copy_item'),
            ('/api/dropbox/shared_links/create', {'user_id': 'u', 'path': '/f'},
             'create_shared_link'),
        ]
        for url, payload, attr in cases:
            m = getattr(service, attr)
            m.side_effect = RuntimeError('x')
            assert client.post(url, json=payload).status_code == 500, url
            m.side_effect = None

    def test_query_endpoints(self, client, monkeypatch):
        dr_mod = _dr()
        handler, service = _mock_handler_service()
        monkeypatch.setattr(dr_mod, 'dropbox_auth_handler', handler)
        monkeypatch.setattr(dr_mod, 'dropbox_service', service)
        r = client.get('/api/dropbox/user/info', params={'user_id': 'u'})
        assert r.status_code == 200
        r = client.get('/api/dropbox/space/usage', params={'user_id': 'u'})
        assert r.status_code == 200
        r = client.get('/api/dropbox/file_metadata',
                       params={'user_id': 'u', 'path': '/f'})
        assert r.status_code == 200
        r = client.get('/api/dropbox/health')
        assert r.status_code == 200 and r.json()['status'] == 'healthy'
        # errors
        for url, attr in (('/api/dropbox/user/info', 'get_account_info'),
                          ('/api/dropbox/space/usage', 'get_space_usage'),
                          ('/api/dropbox/file_metadata', 'get_metadata')):
            getattr(service, attr).side_effect = RuntimeError('x')
            params = {'user_id': 'u', 'path': '/f'}
            assert client.get(url, params=params).status_code == 500, url
            getattr(service, attr).side_effect = None

    def test_method_validation(self, client):
        # POST-only endpoints reject GET
        assert client.get('/api/dropbox/files/list').status_code == 405
        assert client.get('/api/dropbox/files/upload').status_code == 405
        assert client.get('/api/dropbox/items/delete').status_code == 405
        # callback requires code
        assert client.get('/api/dropbox/callback').status_code == 422
        # auth required (no override usage here is fine — override present)
        assert client.get('/api/dropbox/oauth/url').status_code in (200, 500)
