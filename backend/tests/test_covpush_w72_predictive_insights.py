# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/predictive_insights (standalone, zero LLM spend,
no network, no real DB).

Closes the remaining gaps: response-time prediction with historical patterns
(high/mid/low hourly-probability multipliers, platform match/mismatch,
urgency multipliers, HIGH/MEDIUM/LOW confidence tiers), channel recommendation
(urgent email->real-time switch, urgent real-time, preferred message type,
default fallback), bottleneck detection (all three severity bands, empty
threads, unparseable last timestamps, severity ordering, generated actions),
user-pattern analysis edge branches (too few messages, no timestamps, no
response times), hourly probability math, message-type extraction, and
_parse_timestamp branches.

Also proves two REAL robustness bugs (fixed in the source):
- detect_bottlenecks raised TypeError ("can't subtract offset-naive and
  offset-aware datetimes") when thread timestamps were naive (tz-less) ISO
  strings, which is the norm for cross-platform message data. _parse_timestamp
  now normalizes naive datetimes to UTC, and the sort-key fallbacks use a
  UTC-aware datetime.min so mixed aware/naive keys never collide.
- get_insights_summary raised statistics.StatisticsError when every user
  pattern had avg_response_time == 0 (statistics.mean([]) on a non-empty
  user_patterns dict). The mean is now guarded by the filtered list itself.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.predictive_insights import (
    PredictiveInsightsEngine,
    RecommendationConfidence,
    UrgencyLevel,
    get_predictive_insights_engine,
)


@pytest.fixture()
def engine():
    return PredictiveInsightsEngine(min_data_points=2)


def _ts(days_ago, h=10, m=0, s=0):
    """Deterministic ISO timestamp at hour h (default 10:00 UTC)."""
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return base.replace(hour=h, minute=m, second=s, microsecond=0).isoformat()


def _ts_ago(days_ago):
    """Relative timestamp keeping now's time-of-day (bottleneck waits)."""
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _ts_naive(days_ago):
    """tz-less ISO timestamp (the format real cross-platform data uses)."""
    base = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return base.replace(tzinfo=None).isoformat()


# ============================================================================
# analyze_historical_data
# ============================================================================

def test_analyze_historical_data_groups_users_and_threads(engine):
    messages = [
        {"sender_name": "alice", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "alice", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, m=1)},
        {"sender_name": "bob", "thread_id": "t2", "platform": "teams", "timestamp": _ts(0)},
        {"sender": "carol", "conversation_id": "t3", "platform": "gmail", "timestamp": _ts(0)},
    ]
    engine.analyze_historical_data(messages)
    # alice (2 msgs) gets a pattern; bob/carol (1 each) don't
    assert "alice" in engine.user_patterns
    assert "bob" not in engine.user_patterns
    assert "carol" not in engine.user_patterns
    assert set(engine.thread_activity) == {"t1", "t2", "t3"}


# ============================================================================
# predict_response_time
# ============================================================================

def test_predict_no_pattern_platform_defaults(engine):
    cases = {"slack": 1800, "teams": 2400, "gmail": 86400, "outlook": 86400, "sms": 3600}
    for platform, base in cases.items():
        pred = engine.predict_response_time("nobody", platform, UrgencyLevel.MEDIUM)
        assert pred.predicted_seconds == base
        assert pred.confidence == RecommendationConfidence.LOW
        assert pred.factors["data_available"] is False
        assert pred.user_id == "nobody"


def test_predict_no_pattern_urgency_multipliers(engine):
    mults = {UrgencyLevel.LOW: 1.5, UrgencyLevel.MEDIUM: 1.0, UrgencyLevel.HIGH: 0.5, UrgencyLevel.URGENT: 0.25}
    for urgency, mult in mults.items():
        pred = engine.predict_response_time("nobody", "slack", urgency)
        assert pred.predicted_seconds == 1800 * mult


def test_predict_no_pattern_default_time_of_day(engine):
    pred = engine.predict_response_time("nobody", "teams")
    assert pred.predicted_seconds == 2400


def _build_pattern(engine, messages):
    engine.analyze_historical_data(messages)
    return engine.user_patterns


def test_predict_with_pattern_high_probability(engine):
    # response_prob 1.0 (>0.7) -> 0.5x; platform match -> 1.0x; URGENT -> 0.4x
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10, 1)},
    ])
    pred = engine.predict_response_time("u1", "slack", UrgencyLevel.URGENT, _dt(10))
    assert pred.predicted_seconds == 60 * 0.5 * 1.0 * 0.4
    assert pred.factors["data_available"] is True
    assert pred.factors["platform_match"] is True
    assert pred.factors["hour_of_day"] == 10
    assert pred.factors["response_probability"] == 1.0


def test_predict_with_pattern_mid_probability(engine):
    # hours 10,10,11,11 -> P(10)=0.5 (0.4 < p <= 0.7) -> 1.0x; platform mismatch -> 1.5x; HIGH -> 0.7x
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10, 5)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 11)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 11, 5)},
    ])
    pred = engine.predict_response_time("u1", "teams", UrgencyLevel.HIGH, _dt(10))
    assert pred.predicted_seconds == 1300 * 1.0 * 1.5 * 0.7
    assert pred.factors["platform_match"] is False
    assert pred.confidence == RecommendationConfidence.LOW  # 1 thread < min_data_points


def test_predict_with_pattern_low_probability(engine):
    # hours 10,10,11,11,12 -> P(12)=0.2 (<=0.4) -> 2.0x
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 10, 1)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 11)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 11, 1)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 12)},
    ])
    pred = engine.predict_response_time("u1", "slack", UrgencyLevel.LOW, _dt(12))
    assert pred.predicted_seconds == 1800 * 2.0 * 1.0 * 1.2
    assert pred.confidence == RecommendationConfidence.LOW  # 1 thread < min_data_points


def _dt(hour, minute=0):
    return datetime(2026, 8, 13, hour, minute, 0, tzinfo=timezone.utc)


def test_predict_confidence_high_many_threads(engine):
    messages = []
    for i in range(50):
        messages.append({"sender_name": "u1", "thread_id": f"t{i}", "platform": "slack", "timestamp": _ts(0, 10)})
        messages.append({"sender_name": "u1", "thread_id": f"t{i}", "platform": "slack", "timestamp": _ts(0, 10, 1)})
    _build_pattern(engine, messages)
    pred = engine.predict_response_time("u1", "slack", UrgencyLevel.MEDIUM, _dt(10))
    assert pred.confidence == RecommendationConfidence.HIGH


# ============================================================================
# recommend_channel
# ============================================================================

def test_recommend_channel_no_pattern(engine):
    rec = engine.recommend_channel("nobody", "general", UrgencyLevel.MEDIUM)
    assert rec.recommended_platform == "slack"
    assert rec.reason == "No historical data available - using default"
    assert rec.confidence == RecommendationConfidence.LOW
    assert rec.alternatives == ["teams", "gmail"]


def _pattern_engine(engine, platform, hours=(10, 12)):
    msgs = [
        {"sender_name": "u1", "thread_id": "t1", "platform": platform, "timestamp": _ts(0, h)}
        for h in hours
    ]
    msgs.append({"sender_name": "u1", "thread_id": "t1", "platform": platform, "timestamp": _ts(0, hours[0], 1)})
    _build_pattern(engine, msgs)
    return engine


def test_recommend_channel_urgent_email_switches_to_slack(engine):
    _pattern_engine(engine, "gmail")
    rec = engine.recommend_channel("u1", "general", UrgencyLevel.URGENT)
    assert rec.recommended_platform == "slack"
    assert rec.reason == "Urgent message - switching to real-time platform"


def test_recommend_channel_urgent_real_time(engine):
    _pattern_engine(engine, "slack")
    rec = engine.recommend_channel("u1", "general", UrgencyLevel.URGENT)
    assert rec.recommended_platform == "slack"
    assert rec.reason == "Urgent message - using most active platform"


def test_recommend_channel_preferred_message_type(engine):
    engine2 = _pattern_engine(engine, "teams")
    # messages contain no type keywords -> preferred is ["general"]
    rec = engine2.recommend_channel("u1", "general", UrgencyLevel.MEDIUM)
    assert rec.reason == "Platform matches user's preferred message types"


def test_recommend_channel_fallback_reason(engine):
    _pattern_engine(engine, "slack")
    rec = engine.recommend_channel("u1", "file_share", UrgencyLevel.MEDIUM)
    assert rec.reason == "User's most active platform"
    assert rec.alternatives == ["teams", "gmail", "outlook"]
    assert rec.expected_response_time is not None


def test_recommend_channel_low_confidence_zero_avg(engine):
    # single message per thread -> no response times -> avg_response_time == 0
    engine.analyze_historical_data([
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t2", "platform": "slack", "timestamp": _ts(1)},
    ])
    rec = engine.recommend_channel("u1", "general", UrgencyLevel.MEDIUM)
    assert rec.confidence == RecommendationConfidence.LOW
    assert rec.recommended_platform == "slack"


# ============================================================================
# detect_bottlenecks
# ============================================================================

def test_detect_bottlenecks_all_severities(engine):
    engine.thread_activity.update({
        "urgent": [
            {"sender_name": "alice", "platform": "slack", "timestamp": _ts_ago(5)},  # ~5 days
        ],
        "high": [
            {"sender_name": "bob", "platform": "teams", "timestamp": _ts_ago(2)},  # ~2 days
        ],
        "medium": [
            {"sender_name": "carol", "platform": "gmail", "timestamp": _ts_ago(1)},  # ~1 day
        ],
        "fresh": [
            {"sender_name": "dan", "platform": "slack", "timestamp": _ts_ago(0)},  # < 24h
        ],
        "empty": [],
    })
    alerts = engine.detect_bottlenecks(threshold_hours=24)
    severities = [a.severity for a in alerts]
    assert severities == [UrgencyLevel.URGENT, UrgencyLevel.HIGH, UrgencyLevel.MEDIUM]
    assert alerts[0].thread_id == "urgent"
    assert alerts[0].affected_users == ["alice"]
    assert alerts[0].platform == "slack"
    assert "hours ago" in alerts[0].description
    assert alerts[0].suggested_action == "Escalate to alternative channel and notify alice"
    assert alerts[1].suggested_action == "Send reminder to bob via different platform"
    assert alerts[2].suggested_action == "Consider sending follow-up to carol"


def test_detect_bottlenecks_no_alert_when_recent(engine):
    engine.thread_activity["t1"] = [
        {"sender_name": "alice", "platform": "slack", "timestamp": _ts_ago(0)},
    ]
    assert engine.detect_bottlenecks(threshold_hours=24) == []


def test_detect_bottlenecks_unparseable_last_timestamp(engine):
    engine.thread_activity["t1"] = [
        {"sender_name": "alice", "platform": "slack", "timestamp": "garbage"},
    ]
    assert engine.detect_bottlenecks(threshold_hours=24) == []


def test_detect_bottlenecks_naive_timestamps_no_crash(engine):
    """BUG REGRESSION: tz-less ISO strings crashed the aware-now subtraction
    with TypeError ('can't subtract offset-naive and offset-aware')."""
    engine.thread_activity["t1"] = [
        {"sender_name": "alice", "platform": "slack", "timestamp": _ts_naive(5)},
    ]
    alerts = engine.detect_bottlenecks(threshold_hours=24)
    assert len(alerts) == 1
    assert alerts[0].thread_id == "t1"


# ============================================================================
# get_user_pattern / get_insights_summary
# ============================================================================

def test_get_user_pattern(engine):
    assert engine.get_user_pattern("u1") is None
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, m=1)},
    ])
    assert engine.get_user_pattern("u1") is not None


def test_get_insights_summary_empty(engine):
    summary = engine.get_insights_summary()
    assert summary == {
        "users_analyzed": 0,
        "threads_tracked": 0,
        "bottlenecks_detected": 0,
        "active_patterns": 0,
        "avg_response_time_all_users": 0,
    }


def test_get_insights_summary_with_data(engine):
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, m=1)},
        {"sender_name": "u2", "thread_id": "t2", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u2", "thread_id": "t2", "platform": "slack", "timestamp": _ts(0, m=2)},
    ])
    summary = engine.get_insights_summary()
    assert summary["users_analyzed"] == 2
    assert summary["threads_tracked"] == 2
    assert summary["active_patterns"] == 2
    assert summary["avg_response_time_all_users"] == 90.0


def test_get_insights_summary_all_zero_avg_no_crash(engine):
    """BUG REGRESSION: patterns exist but every avg_response_time == 0 ->
    statistics.mean([]) raised StatisticsError."""
    _build_pattern(engine, [
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t2", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t3", "platform": "slack", "timestamp": _ts(0)},
    ])
    summary = engine.get_insights_summary()
    assert summary["users_analyzed"] == 1
    assert summary["active_patterns"] == 0
    assert summary["avg_response_time_all_users"] == 0


# ============================================================================
# _analyze_user_patterns internals
# ============================================================================

def test_user_patterns_too_few_messages(engine):
    engine.analyze_historical_data([
        {"sender_name": "solo", "thread_id": "t1", "timestamp": _ts(0)},
    ])
    assert "solo" not in engine.user_patterns


def test_user_patterns_no_timestamps(engine):
    engine.analyze_historical_data([
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack"},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack"},
    ])
    assert "u1" not in engine.user_patterns


def test_user_patterns_no_response_times(engine):
    engine.analyze_historical_data([
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0)},
        {"sender_name": "u1", "thread_id": "t2", "platform": "teams", "timestamp": _ts(0)},
    ])
    pattern = engine.user_patterns["u1"]
    assert pattern.avg_response_time == 0
    assert pattern.most_active_platform == "slack"  # deterministic tie -> first max


def test_user_patterns_full(engine):
    engine.analyze_historical_data([
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 9),
         "content": "urgent deadline for the project"},
        {"sender_name": "u1", "thread_id": "t1", "platform": "slack", "timestamp": _ts(0, 9, 1),
         "content": "please review the attached document"},
        {"sender_name": "u1", "thread_id": "t2", "platform": "teams", "timestamp": _ts(0, 9, 2),
         "content": "can we schedule a meeting to sync?"},
    ])
    pattern = engine.user_patterns["u1"]
    assert pattern.most_active_hours == [9]
    assert pattern.most_active_platform == "slack"
    assert pattern.response_probability_by_hour == {9: 1.0}
    assert "urgent" in pattern.preferred_message_types
    assert "file_share" in pattern.preferred_message_types
    assert "meeting" in pattern.preferred_message_types


# ============================================================================
# _calculate_response_times / _calculate_hourly_probabilities /
# _extract_message_types / _generate_bottleneck_action / _parse_timestamp
# ============================================================================

def test_calculate_response_times_filters(engine):
    times = engine._calculate_response_times([
        {"thread_id": "t1", "timestamp": _ts(0, 9, 0, 0)},
        {"thread_id": "t1", "timestamp": _ts(0, 9, 0, 10)},  # 10s -> too fast
        {"thread_id": "t1", "timestamp": _ts(0, 10, 0)},     # 50 min -> ok
        {"thread_id": "t1", "timestamp": _ts(3, 9, 0)},      # > 24h -> excluded
        {"thread_id": "t2", "timestamp": _ts(0, 9, 0)},      # single -> skipped
    ])
    assert times == [3590.0]


def test_calculate_hourly_probabilities(engine):
    assert engine._calculate_hourly_probabilities([]) == {}
    probs = engine._calculate_hourly_probabilities([9, 9, 10])
    assert probs == {9: 2 / 3, 10: 1 / 3}


def test_extract_message_types(engine):
    messages = [
        {"content": "URGENT: fix this asap"},
        {"content": "please review the attached file"},
        {"content": "meeting at 3pm?"},
        {"content": "how to run this task?"},
        {"content": "nothing special here"},
    ]
    types = engine._extract_message_types(messages)
    assert types[0] in ("urgent", "file_share", "meeting", "question")
    assert engine._extract_message_types([{"content": "hi"}]) == ["general"]


def test_generate_bottleneck_action(engine):
    assert engine._generate_bottleneck_action(UrgencyLevel.URGENT, "slack", "a") == "Escalate to alternative channel and notify a"
    assert engine._generate_bottleneck_action(UrgencyLevel.HIGH, "teams", "b") == "Send reminder to b via different platform"
    assert engine._generate_bottleneck_action(UrgencyLevel.MEDIUM, "gmail", "c") == "Consider sending follow-up to c"


def test_parse_timestamp_branches(engine):
    aware = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 8, 13, 10, 0, 0)
    assert engine._parse_timestamp(None) is None
    assert engine._parse_timestamp(aware) is aware
    assert engine._parse_timestamp(naive) == aware  # normalized
    assert engine._parse_timestamp("2026-08-13T10:00:00") == naive.replace(tzinfo=timezone.utc)
    assert engine._parse_timestamp("garbage") is None
    assert engine._parse_timestamp(99) is None


def test_singleton_helper():
    engine = get_predictive_insights_engine()
    assert isinstance(engine, PredictiveInsightsEngine)
    assert engine is get_predictive_insights_engine()
