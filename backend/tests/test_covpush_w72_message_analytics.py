# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/message_analytics_engine (standalone, zero LLM spend,
no network, no real DB).

Covers the previously-untested branches: hourly peak detection (valid/invalid/
missing timestamps, datetime objects), daily channel aggregation, 7d/30d
summary windows, _parse_timestamp edge branches (datetime passthrough, valid
ISO string, malformed string, non-string), and the module singleton helper.

Also proves two REAL robustness bugs (fixed in the source):
- calculate_response_times crashed with TypeError when a thread mixed
  str + datetime timestamps (raw `sorted()` key compared incompatible types)
  or contained a malformed ISO string (uncaught ValueError in fromisoformat).
  Both now normalize via _parse_timestamp and skip unparseable pairs.
- get_analytics_summary crashed with TypeError (None >= cutoff) when any
  message lacked a timestamp inside a windowed run. Timestamp-less messages
  are now excluded from the window.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.message_analytics_engine import (
    MessageAnalyticsEngine,
    SentimentLevel,
    get_message_analytics_engine,
)


@pytest.fixture()
def engine():
    return MessageAnalyticsEngine()


def _ts(h, m, day=13):
    return datetime(2026, 8, day, h, m, 0, tzinfo=timezone.utc)


# ============================================================================
# Sentiment / stats
# ============================================================================

def test_sentiment_all_levels(engine):
    assert engine.analyze_sentiment("") == SentimentLevel.NEUTRAL
    assert engine.analyze_sentiment("thanks for the great help!") == SentimentLevel.POSITIVE
    assert engine.analyze_sentiment("this is broken, nothing works") == SentimentLevel.NEGATIVE
    assert engine.analyze_sentiment("hello world") == SentimentLevel.NEUTRAL
    # tie -> neutral
    assert engine.analyze_sentiment("great but also bad") == SentimentLevel.NEUTRAL


def test_calculate_message_stats_full(engine):
    messages = [
        {"content": "thanks a lot", "has_attachments": True, "mentions": ["@alice"], "urls": ["http://x"]},
        {"content": "ok", "has_attachments": False, "mentions": [], "urls": []},
        {"content": "terrible bug", "has_attachments": True, "mentions": ["@bob"]},
    ]
    stats = engine.calculate_message_stats(messages)
    assert stats.total_messages == 3
    assert stats.total_words == 6
    assert stats.total_characters == 26
    assert stats.with_attachments == 2
    assert stats.with_mentions == 2
    assert stats.with_urls == 1
    assert stats.sentiment_distribution == {"positive": 1, "negative": 1, "neutral": 1}


# ============================================================================
# Response times (incl. bug regression tests)
# ============================================================================

def test_response_times_within_window(engine):
    messages = [
        {"thread_id": "t1", "timestamp": _ts(10, 0)},
        {"thread_id": "t1", "timestamp": _ts(10, 2)},   # 120s
        {"thread_id": "t1", "timestamp": _ts(10, 10)},  # 480s
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 2
    assert metrics.avg_response_time == 300.0
    assert metrics.median_response_time == 480.0  # impl: response_times[total // 2]
    assert metrics.p95_response_time == 480.0  # < 20 samples -> last
    assert metrics.p99_response_time == 480.0  # < 100 samples -> last


def test_response_times_filters_out_of_window_and_no_thread(engine):
    messages = [
        {"thread_id": "t1", "timestamp": _ts(10, 0)},
        {"thread_id": "t1", "timestamp": _ts(10, 0, day=15)},  # 48h -> excluded
        {"timestamp": _ts(10, 0)},                              # no thread -> ignored
        {"thread_id": "t2", "timestamp": _ts(10, 0)},
        {"thread_id": "t2", "timestamp": _ts(10, 0, day=15)},   # 48h -> excluded
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 0
    assert metrics.avg_response_time == 0.0


def test_response_times_string_timestamps(engine):
    messages = [
        {"thread_id": "t1", "timestamp": "2026-08-13T10:00:00"},
        {"thread_id": "t1", "timestamp": "2026-08-13T10:01:00"},
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 1
    assert metrics.avg_response_time == 60.0


def test_response_times_missing_timestamps_no_crash(engine):
    messages = [
        {"thread_id": "t1", "timestamp": _ts(10, 0)},
        {"thread_id": "t1"},  # no timestamp
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 0


def test_response_times_mixed_timestamp_types_no_crash(engine):
    """BUG REGRESSION: str + datetime in the same thread crashed the raw
    sorted() key with TypeError ('<' not supported between str and datetime)."""
    messages = [
        {"thread_id": "t1", "timestamp": datetime(2026, 8, 13, 10, 0, 0)},
        {"thread_id": "t1", "timestamp": "2026-08-13T10:01:00"},
        {"thread_id": "t1", "timestamp": "2026-08-13T10:02:00"},
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 2
    assert metrics.response_times == [60.0, 60.0]


def test_response_times_malformed_timestamp_no_crash(engine):
    """BUG REGRESSION: a malformed ISO string inside a thread raised an
    uncaught ValueError from datetime.fromisoformat."""
    messages = [
        {"thread_id": "t1", "timestamp": "2026-08-13T10:00:00"},
        {"thread_id": "t1", "timestamp": "not-a-timestamp"},
        {"thread_id": "t1", "timestamp": "2026-08-13T10:05:00"},
    ]
    metrics = engine.calculate_response_times(messages)
    assert metrics.total_responses == 1
    assert metrics.response_times == [300.0]


# ============================================================================
# Thread participation
# ============================================================================

def test_thread_participation(engine):
    messages = [
        {"thread_id": "t1", "sender_name": "alice"},
        {"thread_id": "t1", "sender_name": "alice"},
        {"thread_id": "t1", "sender_name": "bob"},
        {"conversation_id": "t2", "sender_name": "carol"},
        {"sender_name": "no-thread"},
    ]
    participation = engine.analyze_thread_participation(messages)
    assert set(participation) == {"t1", "t2"}
    t1 = participation["t1"]
    assert t1.total_messages == 3
    assert t1.participants == {"alice": 2, "bob": 1}
    assert t1.most_active_participant == "alice"
    assert t1.average_messages_per_user == 1.5
    assert participation["t2"].most_active_participant == "carol"
    assert participation["t2"].average_messages_per_user == 1.0


# ============================================================================
# Peak activity
# ============================================================================

def test_peak_activity_hourly(engine):
    messages = [
        {"timestamp": _ts(9, 0)},
        {"timestamp": "2026-08-13T09:30:00"},
        {"timestamp": _ts(14, 0)},
        {"timestamp": "bad-timestamp"},
        {"timestamp": None},
        {"timestamp": 12345},
    ]
    metrics = engine.detect_peak_activity(messages, period="hourly")
    assert metrics.messages_per_hour == {"09:00": 2, "14:00": 1}
    assert metrics.peak_hours[0] == ("09:00", 2)
    assert metrics.peak_days == []


def test_peak_activity_daily_channels(engine):
    messages = [
        {"timestamp": _ts(9, 0), "channel_id": "c1"},
        {"timestamp": _ts(10, 0), "channel_id": "c1"},
        {"timestamp": "2026-08-14T09:00:00", "channel_id": "c2"},
        {"timestamp": "garbage", "channel_id": "c3"},
        {"timestamp": None},
    ]
    metrics = engine.detect_peak_activity(messages, period="daily")
    assert metrics.messages_per_day == {"2026-08-13": 2, "2026-08-14": 1}
    assert metrics.messages_per_channel == {"c1": 2, "c2": 1}
    assert metrics.peak_days[0][1] == 2
    assert metrics.peak_hours == []


def test_peak_activity_empty(engine):
    metrics = engine.detect_peak_activity([], period="daily")
    assert metrics.peak_days == []
    assert metrics.messages_per_day == {}


def test_peak_activity_unsupported_period(engine):
    metrics = engine.detect_peak_activity([{"timestamp": _ts(9, 0)}], period="weekly")
    assert metrics.messages_per_hour == {}
    assert metrics.messages_per_day == {}


# ============================================================================
# Cross-platform analytics
# ============================================================================

def test_cross_platform_analytics(engine):
    messages = [
        {"platform": "slack", "content": "great work", "has_attachments": True},
        {"platform": "slack", "content": "thanks"},
        {"platform": "teams", "content": "broken"},
        {"content": "orphan"},
    ]
    result = engine.get_cross_platform_analytics(messages)
    assert result["total_messages"] == 4
    assert result["most_active_platform"] == "slack"
    assert result["platforms"]["slack"]["message_count"] == 2
    assert result["platforms"]["slack"]["sentiment"] == {"positive": 2, "negative": 0, "neutral": 0}
    assert result["platforms"]["slack"]["total_attachments"] == 1
    assert result["platforms"]["unknown"]["message_count"] == 1


def test_cross_platform_analytics_empty(engine):
    result = engine.get_cross_platform_analytics([])
    assert result["total_messages"] == 0
    assert result["most_active_platform"] is None
    assert result["platforms"] == {}


# ============================================================================
# Analytics summary (windows)
# ============================================================================

def _fresh_message(hour, minute=0, content="hello"):
    return {"timestamp": datetime.now(timezone.utc) - timedelta(hours=hour, minutes=minute), "content": content}


def test_analytics_summary_24h(engine):
    result = engine.get_analytics_summary([_fresh_message(1), _fresh_message(23), _fresh_message(25)], "24h")
    assert result["time_window"] == "24h"
    assert result["message_stats"]["total_messages"] == 2
    assert result["period"]["start"] is not None


def test_analytics_summary_7d(engine):
    messages = [_fresh_message(23 * 6), _fresh_message(24 * 8)]
    result = engine.get_analytics_summary(messages, "7d")
    assert result["message_stats"]["total_messages"] == 1


def test_analytics_summary_30d(engine):
    messages = [_fresh_message(24 * 10), _fresh_message(24 * 31)]
    result = engine.get_analytics_summary(messages, "30d")
    assert result["message_stats"]["total_messages"] == 1


def test_analytics_summary_all_window(engine):
    messages = [_fresh_message(24 * 100), {"content": "no-ts"}]
    result = engine.get_analytics_summary(messages, "all")
    assert result["message_stats"]["total_messages"] == 2
    assert result["period"]["start"] is None


def test_analytics_summary_missing_timestamp_no_crash(engine):
    """BUG REGRESSION: a message without a timestamp crashed the windowed
    filter with TypeError (None >= cutoff)."""
    messages = [_fresh_message(1), {"content": "no-ts"}]
    result = engine.get_analytics_summary(messages, "24h")
    assert result["message_stats"]["total_messages"] == 1


def test_analytics_summary_structure(engine):
    # Compute `now` ONCE — three separate now() calls can straddle UTC
    # midnight, landing the two messages in different day buckets and
    # breaking the peak_days assertion (batch runs cross midnight).
    now = datetime.now(timezone.utc)
    messages = [
        {"timestamp": now - timedelta(minutes=10), "content": "great"},
        {"timestamp": now - timedelta(minutes=5), "content": "bad"},
    ]
    result = engine.get_analytics_summary(messages, "24h")
    assert result["message_stats"]["avg_words_per_message"] == 1.0
    assert result["thread_participation"] == {"total_threads": 0, "avg_messages_per_thread": 0, "most_active_threads": []}
    today = now.strftime("%Y-%m-%d")
    assert result["activity_peaks"]["peak_days"] == [(today, 2)]
    assert result["cross_platform"]["total_messages"] == 2


# ============================================================================
# _parse_timestamp branches
# ============================================================================

def test_parse_timestamp_branches(engine):
    aware = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 8, 13, 10, 0, 0)
    assert engine._parse_timestamp(None) is None
    assert engine._parse_timestamp(aware) is aware
    assert engine._parse_timestamp(naive) == aware  # normalized to UTC
    assert engine._parse_timestamp("2026-08-13T10:00:00") == naive.replace(tzinfo=timezone.utc)
    assert engine._parse_timestamp("2026-08-13T10:00:00+00:00") == aware
    assert engine._parse_timestamp("junk") is None
    assert engine._parse_timestamp(42) is None


def test_singleton_helper():
    engine = get_message_analytics_engine()
    assert isinstance(engine, MessageAnalyticsEngine)
    assert engine is get_message_analytics_engine()
