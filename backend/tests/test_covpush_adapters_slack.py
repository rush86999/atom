"""
Coverage-push + bug-hunt tests for integrations/slack_analytics_engine.py.

TDD target (RED first): get_insights() calls self._get_*_insights helpers that
do not exist -> AttributeError -> get_insights always returns {} for every
metric (feature is dead).
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.slack_analytics_engine import (
    AnalyticsDataPoint,
    AnalyticsGranularity,
    AnalyticsMetric,
    AnalyticsReport,
    AnalyticsTimeRange,
    LLMSentiment,
    LLMTopics,
    SlackAnalyticsEngine,
)


class FakeRedis:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value


def _engine(**cfg):
    cfg.setdefault("database", None)
    with patch("integrations.slack_analytics_engine.get_llm_service",
               return_value=MagicMock()):
        return SlackAnalyticsEngine(cfg)


def _point(ts, value, metric=AnalyticsMetric.MESSAGE_VOLUME, dims=None):
    return AnalyticsDataPoint(timestamp=ts, metric=metric, value=value,
                              dimensions=dims or {})


def _raw(**over):
    item = {
        "timestamp": "2026-01-01T10:00:00+00:00",
        "text": "hello team #launch",
        "user_id": "u1",
        "workspace_id": "w1",
        "channel_id": "c1",
        "reactions": [{"name": "thumbsup", "count": 2}],
        "reply_count": 1,
        "mentions": ["u2"],
        "files": [{"filetype": "pdf", "size": 100}],
        "response_time_seconds": 5,
        "thread_ts": "123.456",
    }
    item.update(over)
    return item


class TestSlackModelsAndBasics:
    def test_analytics_time_range(self):
        assert AnalyticsTimeRange.LAST_7_DAYS.value == "last_7_days"
        assert AnalyticsTimeRange.CUSTOM.value == "custom"

    def test_analytics_metric(self):
        assert AnalyticsMetric.FILE_SHARING.value == "file_sharing"
        assert len(list(AnalyticsMetric)) == 10

    def test_granularity(self):
        assert AnalyticsGranularity.MINUTE.value == "minute"
        assert AnalyticsGranularity.WEEK.value == "week"

    def test_data_point_post_init(self):
        dp = AnalyticsDataPoint(timestamp=datetime(2026, 1, 1),
                                metric=AnalyticsMetric.SENTIMENT, value=1)
        assert dp.timestamp.tzinfo is not None
        assert dp.dimensions == {} and dp.metadata == {}

    def test_report_post_init(self):
        r = AnalyticsReport(
            id="r1", name="n", description="d",
            metrics=[AnalyticsMetric.MESSAGE_VOLUME],
            time_range=AnalyticsTimeRange.TODAY,
            granularity=AnalyticsGranularity.DAY,
            created_by="u1")
        assert r.filters == {} and r.visualizations == []
        assert r.recipients == [] and r.created_at.tzinfo is not None
        assert r.is_scheduled is False

    def test_init(self):
        e = _engine()
        assert e.cache_ttl == 300
        assert e.llm_service is not None
        assert len(e.processors) == 10
        assert e.training_texts == []

    def test_generate_cache_key(self):
        e = _engine()
        key = e._generate_cache_key(
            AnalyticsMetric.MESSAGE_VOLUME, AnalyticsTimeRange.TODAY,
            AnalyticsGranularity.HOUR, {"a": 1}, "w1", ["c2", "c1"], ["u2", "u1"])
        parts = key.split("|")
        assert parts[0] == "message_volume"
        assert parts[5] == "c1,c2"
        assert parts[6] == "u1,u2"

    def test_get_analytics_cached(self):
        e = _engine()
        redis = FakeRedis()
        e.redis_client = redis
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        key = e._generate_cache_key(AnalyticsMetric.MESSAGE_VOLUME,
                                    AnalyticsTimeRange.TODAY,
                                    AnalyticsGranularity.HOUR, None, None, None, None)
        redis.setex(f"analytics:{key}", 300,
                    json.dumps([asdict(_point(ts, 3))], default=str))
        data = asyncio.run(e.get_analytics(AnalyticsMetric.MESSAGE_VOLUME,
                                           AnalyticsTimeRange.TODAY))
        assert len(data) == 1
        assert data[0].value == 3

    def test_get_analytics_processor_path(self):
        e = _engine()
        e._fetch_data = AsyncMock(return_value=[_raw()])
        data = asyncio.run(e.get_analytics(AnalyticsMetric.MESSAGE_VOLUME,
                                           AnalyticsTimeRange.TODAY))
        assert len(data) == 1
        assert data[0].metric == AnalyticsMetric.MESSAGE_VOLUME

    def test_get_analytics_unknown_metric(self):
        e = _engine()
        e.processors = {}
        assert asyncio.run(e.get_analytics(AnalyticsMetric.MESSAGE_VOLUME,
                                           AnalyticsTimeRange.TODAY)) == []

    def test_get_analytics_exception(self):
        e = _engine()
        e._fetch_data = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_analytics(AnalyticsMetric.MESSAGE_VOLUME,
                                           AnalyticsTimeRange.TODAY)) == []

    def test_cache_analytics_and_get(self):
        e = _engine()
        redis = FakeRedis()
        e.redis_client = redis
        e._cache_analytics("k1", [_point(datetime(2026, 1, 1, tzinfo=timezone.utc), 5)])
        data = e._get_cached_analytics("k1")
        assert data[0].value == 5
        assert e._get_cached_analytics("nope") is None

    def test_fetch_data_with_db(self):
        e = _engine()
        db = MagicMock()
        db.execute.return_value.fetchall.return_value = [
            {"timestamp": "2026-01-01T10:00:00+00:00", "text": "hi"},
        ]
        e.database = db
        data = asyncio.run(e._fetch_data(AnalyticsMetric.MESSAGE_VOLUME,
                                         AnalyticsTimeRange.TODAY, None, None,
                                         None, None))
        assert data[0]["text"] == "hi"

    def test_fetch_data_mock(self):
        e = _engine()
        data = asyncio.run(e._fetch_data(AnalyticsMetric.MESSAGE_VOLUME,
                                         AnalyticsTimeRange.TODAY, None, None,
                                         None, None))
        assert data[0]["timestamp"] is not None

    def test_fetch_data_error(self):
        e = _engine()
        e.database = MagicMock()
        e.database.execute.side_effect = Exception("boom")
        assert asyncio.run(e._fetch_data(AnalyticsMetric.MESSAGE_VOLUME,
                                         AnalyticsTimeRange.TODAY, None, None,
                                         None, None)) == []

    def test_get_date_range(self):
        e = _engine()
        now = datetime.now(timezone.utc)
        s, en = e._get_date_range(AnalyticsTimeRange.TODAY)
        assert s.hour == 0 and en >= s
        s2, en2 = e._get_date_range(AnalyticsTimeRange.YESTERDAY)
        assert (now - s2).days >= 1
        assert en2.hour == 23
        s3, _ = e._get_date_range(AnalyticsTimeRange.LAST_7_DAYS)
        assert (now - s3).days >= 6
        s4, _ = e._get_date_range(AnalyticsTimeRange.LAST_30_DAYS)
        assert (now - s4).days >= 29
        s5, _ = e._get_date_range(AnalyticsTimeRange.LAST_90_DAYS)
        assert (now - s5).days >= 89
        s6, _ = e._get_date_range(AnalyticsTimeRange.CUSTOM)
        assert (now - s6).days >= 29

    def test_build_query(self):
        e = _engine()
        q = e._build_query(AnalyticsMetric.MESSAGE_VOLUME,
                           datetime.now(timezone.utc), datetime.now(timezone.utc),
                           None, None, None, None)
        assert "slack_messages" in q

    def test_parse_timestamp(self):
        e = _engine()
        assert e._parse_timestamp("1767268800.0") is not None
        assert e._parse_timestamp("2026-01-01T10:00:00Z").tzinfo is not None
        assert e._parse_timestamp("2026-01-01 10:00:00") is not None
        assert e._parse_timestamp("") is None
        assert e._parse_timestamp("garbage") is None
        assert e._parse_timestamp("2026-13-99T99:99:99") is None

    def test_group_by_hour_day_raw(self):
        e = _engine()
        items = [_raw(timestamp="2026-01-01T10:15:00+00:00"),
                 _raw(timestamp="2026-01-01T10:45:00+00:00"),
                 _raw(timestamp="2026-01-01T11:00:00+00:00"),
                 {"timestamp": "garbage"}]
        by_hour = e._group_by_hour(items, "timestamp")
        assert len(by_hour) == 2
        by_day = e._group_by_day(items, "timestamp")
        assert len(by_day) == 1
        by_raw = e._group_by_raw_timestamp(items)
        assert len(by_raw) == 3


class TestSlackInsights:
    def test_get_insights_all_metrics(self):
        e = _engine()
        e._fetch_data = AsyncMock(return_value=[_raw(), _raw(text="bad day #ops")])
        e.llm_service.generate_structured = AsyncMock(
            return_value=LLMSentiment(score=0.2, label="positive", confidence=0.8))
        for metric in (AnalyticsMetric.MESSAGE_VOLUME, AnalyticsMetric.USER_ACTIVITY,
                       AnalyticsMetric.ENGAGEMENT, AnalyticsMetric.RESPONSE_TIME,
                       AnalyticsMetric.SENTIMENT):
            result = asyncio.run(e.get_insights(metric, AnalyticsTimeRange.TODAY))
            assert result.get("metric") == metric.value, metric
            assert result.get("data_points") is not None

    def test_get_insights_empty(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[])
        assert asyncio.run(e.get_insights(AnalyticsMetric.MESSAGE_VOLUME,
                                          AnalyticsTimeRange.TODAY)) == {}

    def test_get_insights_exception(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_insights(AnalyticsMetric.MESSAGE_VOLUME,
                                          AnalyticsTimeRange.TODAY)) == {}

    def test_generate_report(self):
        e = _engine()
        report = AnalyticsReport(
            id="r1", name="Weekly", description="d",
            metrics=[AnalyticsMetric.MESSAGE_VOLUME],
            time_range=AnalyticsTimeRange.LAST_7_DAYS,
            granularity=AnalyticsGranularity.DAY,
            created_by="u1", visualizations=["bar"])
        e.reports["r1"] = report
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 3)])
        e.get_insights = AsyncMock(return_value={"metric": "message_volume"})
        result = asyncio.run(e.generate_report("r1"))
        assert result["name"] == "Weekly"
        assert len(result["metrics"]) == 1
        assert result["metrics"][0]["data"][0]["value"] == 3
        assert result["visualizations"] == ["bar"]

    def test_generate_report_metric_error(self):
        e = _engine()
        report = AnalyticsReport(
            id="r1", name="n", description="d",
            metrics=[AnalyticsMetric.MESSAGE_VOLUME],
            time_range=AnalyticsTimeRange.TODAY,
            granularity=AnalyticsGranularity.DAY,
            created_by="u1")
        e.reports["r1"] = report
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        result = asyncio.run(e.generate_report("r1"))
        assert "error" in result["metrics"][0]

    def test_generate_report_not_found(self):
        e = _engine()
        result = asyncio.run(e.generate_report("missing"))
        assert "error" in result


class TestSlackProcessors:
    async def test_message_volume_hour_day_raw(self):
        e = _engine()
        items = [_raw(timestamp="2026-01-01T10:15:00+00:00"),
                 _raw(timestamp="2026-01-01T10:45:00+00:00")]
        for g, expected in ((AnalyticsGranularity.HOUR, 2),
                            (AnalyticsGranularity.DAY, 2),
                            (AnalyticsGranularity.MINUTE, 1)):
            out = await e._process_message_volume(items, g)
            assert len(out) >= 1
            assert out[0].value == expected
            assert out[0].dimensions["workspace_id"] == "w1"

    async def test_user_activity(self):
        e = _engine()
        items = [_raw(timestamp="2026-01-01T10:15:00+00:00"),
                 _raw(timestamp="2026-01-01T10:15:30+00:00", user_id="u1"),
                 _raw(timestamp="2026-01-01T11:00:00+00:00", user_id="u1")]
        for g in (AnalyticsGranularity.HOUR, AnalyticsGranularity.DAY,
                  AnalyticsGranularity.MINUTE):
            out = await e._process_user_activity(items, g)
            u1 = [p for p in out if p.dimensions["user_id"] == "u1"]
            assert len(u1) >= 1
            assert u1[0].value >= 1

    async def test_user_activity_no_user(self):
        e = _engine()
        out = await e._process_user_activity([_raw(user_id=None)], AnalyticsGranularity.HOUR)
        assert out == []

    async def test_engagement(self):
        e = _engine()
        out = await e._process_engagement([_raw()], AnalyticsGranularity.HOUR)
        assert out[0].value == 1 * 1 + 1 * 2 + 1 * 3
        assert out[0].dimensions["total_reactions"] == 1

    async def test_response_time(self):
        e = _engine()
        out = await e._process_response_time(
            [_raw(response_time_seconds=4), _raw(response_time_seconds=6)],
            AnalyticsGranularity.HOUR)
        assert out[0].value == 5
        assert out[0].dimensions["min_response_time"] == 4
        assert out[0].dimensions["max_response_time"] == 6
        empty = await e._process_response_time(
            [_raw(response_time_seconds=None)], AnalyticsGranularity.HOUR)
        assert empty == []

    async def test_sentiment(self):
        e = _engine()
        e._analyze_sentiment = AsyncMock(
            side_effect=lambda t: {"score": 0.5} if t else {"score": 0.0})
        out = await e._process_sentiment([_raw(text="good"), _raw(text="")],
                                         AnalyticsGranularity.HOUR)
        assert out[0].value == 0.5
        dist = out[0].dimensions["sentiment_distribution"]
        assert dist["positive"] == 1.0

    async def test_sentiment_empty(self):
        e = _engine()
        out = await e._process_sentiment([_raw(text="")], AnalyticsGranularity.HOUR)
        assert out == []

    async def test_collaboration(self):
        e = _engine()
        out = await e._process_collaboration([_raw()], AnalyticsGranularity.HOUR)
        assert out[0].value == 1 * 2 + 1 * 1 + 1 * 1.5

    async def test_productivity(self):
        e = _engine()
        out = await e._process_productivity(
            [_raw(text="complete the task please"),
             _raw(text="we agreed on this decision")],
            AnalyticsGranularity.HOUR)
        assert out[0].value == 3 + 5
        assert out[0].dimensions["completed_tasks"] == 1
        assert out[0].dimensions["decisions_made"] == 1

    async def test_topics(self):
        e = _engine()
        e._extract_topics = AsyncMock(
            side_effect=lambda t: {"topics": ["launch", "ops"]})
        out = await e._process_topics([_raw(text="hi"), _raw(text="")],
                                      AnalyticsGranularity.HOUR)
        assert set(out[0].value) == {"launch", "ops"}
        assert out[0].dimensions["total_topics"] == 2
        assert out[0].dimensions["topic_frequency"] == {"launch": 1, "ops": 1}

    async def test_reactions(self):
        e = _engine()
        out = await e._process_reactions([_raw()], AnalyticsGranularity.HOUR)
        assert out[0].value == 2
        assert out[0].dimensions["reaction_breakdown"] == {"thumbsup": 2}
        assert out[0].dimensions["unique_reactions"] == 1

    async def test_reactions_empty(self):
        e = _engine()
        out = await e._process_reactions([_raw(reactions=[])], AnalyticsGranularity.HOUR)
        assert out[0].value == 0

    async def test_file_sharing(self):
        e = _engine()
        out = await e._process_file_sharing([_raw()], AnalyticsGranularity.HOUR)
        assert out[0].value == 1
        assert out[0].dimensions["file_type_breakdown"] == {"pdf": 1}
        assert out[0].dimensions["average_file_size"] == 100
        empty = await e._process_file_sharing([_raw(files=[])], AnalyticsGranularity.HOUR)
        assert empty[0].value == 0
        assert empty[0].dimensions["average_file_size"] == 0


class TestSlackAggregations:
    def test_get_top_users(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 5, dims={"user_id": "a"}),
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 1, dims={"user_id": "a"}),
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 9, dims={"user_id": "b"}),
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 2, dims={}),
        ])
        top = asyncio.run(e.get_top_users(AnalyticsMetric.USER_ACTIVITY,
                                          AnalyticsTimeRange.TODAY, limit=1))
        assert top[0]["user_id"] == "b"
        assert top[0]["average_value"] == 9
        assert len(top) == 1

    def test_get_top_users_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_top_users(AnalyticsMetric.USER_ACTIVITY,
                                           AnalyticsTimeRange.TODAY)) == []

    def test_get_top_channels(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 5,
                   dims={"channel_id": "c1"}),
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 5,
                   dims={"channel_id": "c2"}),
        ])
        top = asyncio.run(e.get_top_channels(AnalyticsMetric.MESSAGE_VOLUME,
                                             AnalyticsTimeRange.TODAY))
        assert len(top) == 2

    def test_get_top_channels_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_top_channels(AnalyticsMetric.MESSAGE_VOLUME,
                                              AnalyticsTimeRange.TODAY)) == []

    def test_get_trending_topics(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), ["a", "b"],
                   metric=AnalyticsMetric.TOPICS),
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), "a,c",
                   metric=AnalyticsMetric.TOPICS),
        ])
        top = asyncio.run(e.get_trending_topics(AnalyticsTimeRange.TODAY, limit=2))
        assert top[0]["topic"] == "a"
        assert top[0]["mentions"] == 2

    def test_get_trending_topics_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_trending_topics(AnalyticsTimeRange.TODAY)) == []

    def test_engagement_heatmap(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc), 5,
                   metric=AnalyticsMetric.ENGAGEMENT),
            _point(datetime(2026, 1, 6, 10, 30, tzinfo=timezone.utc), 15,
                   metric=AnalyticsMetric.ENGAGEMENT),
        ])
        hm = asyncio.run(e.get_engagement_heatmap(AnalyticsTimeRange.LAST_7_DAYS))
        assert len(hm["heatmap"]) == 7
        tuesday = [d for d in hm["heatmap"] if d["day"] == "Tuesday"][0]
        assert tuesday["hours"][10]["value"] == 20
        assert tuesday["hours"][10]["normalized"] == 1.0
        assert hm["max_value"] == 20

    def test_engagement_heatmap_empty(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[])
        hm = asyncio.run(e.get_engagement_heatmap(AnalyticsTimeRange.TODAY))
        assert hm["max_value"] == 0
        assert hm["heatmap"][0]["hours"][0]["normalized"] == 1

    def test_engagement_heatmap_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_engagement_heatmap(AnalyticsTimeRange.TODAY)) == {}

    def test_predict_message_volume_insufficient(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 3)])
        result = asyncio.run(e.predict_message_volume())
        assert "error" in result

    def test_predict_message_volume_success(self):
        e = _engine()
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        pts = [_point(base + timedelta(hours=i), float(i % 10)) for i in range(200)]
        e.get_analytics = AsyncMock(return_value=pts)
        result = asyncio.run(e.predict_message_volume(hours_ahead=4))
        assert result["model_used"] == "ai_enhanced_moving_average"
        assert len(result["predictions"]) == 4
        assert result["data_points_used"] == 200
        assert result["confidence_score"] == 0.85

    def test_predict_message_volume_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert "error" in asyncio.run(e.predict_message_volume())

    def test_get_productivity_metrics(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[
            _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 10),
            _point(datetime(2026, 1, 2, tzinfo=timezone.utc), 20),
            _point(datetime(2026, 1, 3, tzinfo=timezone.utc), 30),
        ])
        pm = asyncio.run(e.get_productivity_metrics(AnalyticsTimeRange.LAST_7_DAYS))
        assert pm["overall_productivity"] > 0
        assert pm["message_volume_score"] == pytest.approx(20 / 30)
        assert pm["trends"]["message_volume_trend"] == "increasing"

    def test_get_productivity_metrics_empty(self):
        e = _engine()
        e.get_analytics = AsyncMock(return_value=[])
        pm = asyncio.run(e.get_productivity_metrics(AnalyticsTimeRange.TODAY))
        assert pm["overall_productivity"] == 0

    def test_get_productivity_metrics_error(self):
        e = _engine()
        e.get_analytics = AsyncMock(side_effect=Exception("boom"))
        assert asyncio.run(e.get_productivity_metrics(AnalyticsTimeRange.TODAY)) == {}

    def test_calculate_score(self):
        e = _engine()
        assert e._calculate_score([]) == 0
        pts = [_point(datetime(2026, 1, 1, tzinfo=timezone.utc), 4),
               _point(datetime(2026, 1, 1, tzinfo=timezone.utc), 8)]
        assert e._calculate_score(pts) == pytest.approx(0.75)
        assert e._calculate_score(pts, reverse=True) == pytest.approx(0.25)

    def test_calculate_trends(self):
        e = _engine()
        t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
        inc = e._calculate_trends([("m", [_point(t1, 1), _point(t2, 100)])])
        assert inc["m_trend"] == "increasing"
        assert inc["m_change_percent"] > 0
        dec = e._calculate_trends([("m", [_point(t1, 100), _point(t2, 1)])])
        assert dec["m_trend"] == "decreasing"
        stable = e._calculate_trends([("m", [_point(t1, 10), _point(t2, 11)])])
        assert stable["m_trend"] == "stable"
        insuff = e._calculate_trends([("m", [_point(t1, 1)])])
        assert insuff["m_trend"] == "insufficient_data"
        zero = e._calculate_trends([("m", [_point(t1, 0), _point(t2, 5)])])
        assert zero["m_change_percent"] == 0


class TestSlackLLMHelpers:
    def test_analyze_sentiment_empty(self):
        e = _engine()
        result = asyncio.run(e._analyze_sentiment(""))
        assert result["method"] == "empty"
        assert result["score"] == 0.0

    def test_analyze_sentiment_llm(self):
        e = _engine()
        e.llm_service.generate_structured = AsyncMock(
            return_value=LLMSentiment(score=0.9, label="positive", confidence=0.95))
        result = asyncio.run(e._analyze_sentiment("great work"))
        assert result["method"] == "llm_service"
        assert result["score"] == 0.9
        assert result["label"] == "positive"

    def test_analyze_sentiment_llm_none(self):
        e = _engine()
        e.llm_service.generate_structured = AsyncMock(return_value=None)
        result = asyncio.run(e._analyze_sentiment("meh"))
        assert result["method"] == "fallback"

    def test_analyze_sentiment_llm_fail_fallback(self):
        e = _engine()
        e.llm_service.generate_structured = AsyncMock(side_effect=Exception("llm down"))
        result = asyncio.run(e._analyze_sentiment("meh"))
        assert result["method"] == "fallback"
        assert result["score"] == 0.0

    def test_get_sentiment_distribution(self):
        e = _engine()
        assert e._get_sentiment_distribution([]) == {"positive": 0, "neutral": 0, "negative": 0}
        dist = e._get_sentiment_distribution([0.5, -0.5, 0.0])
        assert dist == {"positive": 1 / 3, "neutral": 1 / 3, "negative": 1 / 3}
        dist2 = e._get_sentiment_distribution([0.2, 0.0, -0.2])
        assert dist2 == {"positive": 1 / 3, "neutral": 1 / 3, "negative": 1 / 3}

    def test_extract_topics_empty(self):
        e = _engine()
        result = asyncio.run(e._extract_topics(""))
        assert result["method"] == "empty"

    def test_extract_topics_llm(self):
        e = _engine()
        e.llm_service.generate_structured = AsyncMock(
            return_value=LLMTopics(topics=["launch", "ops"], confidence=0.9))
        result = asyncio.run(e._extract_topics("we launch ops"))
        assert result["method"] == "llm_service"
        assert result["count"] == 2

    def test_extract_topics_fallback(self):
        e = _engine()
        e.llm_service.generate_structured = AsyncMock(side_effect=Exception("llm down"))
        result = asyncio.run(e._extract_topics("talk about #launch and #ops"))
        assert result["method"] == "keyword_fallback"
        assert result["topics"] == ["launch", "ops"]


class TestSlackLDATraining:
    def test_train_lda(self):
        e = _engine()
        texts = [
            "alpha beta gamma delta", "alpha beta gamma omega",
            "alpha beta delta omega", "gamma delta omega alpha",
            "beta gamma delta omega", "alpha alpha beta gamma",
            "delta delta omega alpha", "beta beta gamma omega",
            "alpha omega delta gamma", "beta delta omega gamma",
        ]
        result = e.train_lda_model(texts, num_topics=2)
        assert result["success"] is True
        assert result["num_documents"] == 10
        assert result["vocabulary_size"] > 0
        assert len(result["topic_words"]) == 2
        assert e.lda_model is not None
        assert e.topic_vocab is not None

    def test_train_lda_error(self):
        e = _engine()
        result = e.train_lda_model(["only one document"], num_topics=2)
        assert result["success"] is False

    def test_add_training_texts(self):
        e = _engine()
        count = e.add_training_texts(["a", "b"])
        assert count == 2
        assert len(e.training_texts_timestamps) == 2
        ts = datetime(2026, 1, 1, tzinfo=timezone.utc)
        e.add_training_texts(["c"], timestamps=[ts])
        assert e.training_texts_timestamps[-1] == ts

    def test_get_training_corpus_size(self):
        e = _engine()
        info = e.get_training_corpus_size()
        assert info["total_texts"] == 0
        assert info["can_train_lda"] is False
        assert info["recommended_topics"] == 0
        e.add_training_texts(["x"] * 25)
        info = e.get_training_corpus_size()
        assert info["recommended_topics"] >= 3
        assert info["can_train_lda"] is True

    def test_generate_mock_data(self):
        e = _engine()
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data = e._generate_mock_data(AnalyticsMetric.MESSAGE_VOLUME, start,
                                     start + timedelta(hours=2))
        assert len(data) == 3
        data2 = e._generate_mock_data(AnalyticsMetric.SENTIMENT, start, start)
        assert data2[0]["value"] is not None
