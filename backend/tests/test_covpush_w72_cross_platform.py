# -*- coding: utf-8 -*-
"""Coverage wave 72 — core/cross_platform_correlation (pure-python engine,
no network, no real DB).

Closes the remaining gaps: empty-thread metadata skip, temporal correlation
when a candidate thread lacks timestamps, content correlation when a
candidate thread has no keywords, empty/overlapping merge branches, unified
timeline lookup miss, and invalid-string timestamp parsing. Also exercises
the full end-to-end pipeline (all four strategies + merge + timeline) with
realistic mixed-platform messages.
"""
from datetime import datetime, timedelta, timezone

import pytest

from core.cross_platform_correlation import (
    CorrelationStrength,
    CrossPlatformCorrelationEngine,
    CrossPlatformLink,
    LinkedConversation,
    get_cross_platform_correlation_engine,
)


@pytest.fixture()
def engine():
    return CrossPlatformCorrelationEngine(similarity_threshold=0.3)


def _msg(platform, thread, sender, content, ts, sender_email=None, mentions=None):
    msg = {
        "platform": platform,
        "thread_id": thread,
        "sender_name": sender,
        "content": content,
        "timestamp": ts,
    }
    if sender_email:
        msg["sender_email"] = sender_email
    if mentions:
        msg["mentions"] = mentions
    return msg


def _ts(days_ago=0, h=10, m=0):
    return (datetime(2026, 8, 13, h, m, 0) - timedelta(days=days_ago)).isoformat()


# ============================================================================
# End-to-end pipeline
# ============================================================================

def test_correlate_conversations_full_pipeline(engine):
    """Two slack threads + one teams thread sharing participants -> linked;
    a gmail thread referencing slack within the hour -> reference-linked."""
    messages = [
        _msg("slack", "c1", "alice", "urgent deadline", _ts(0, 9, 0), sender_email="alice@x.com"),
        _msg("slack", "c1", "bob", "deploy the release", _ts(0, 9, 5), sender_email="bob@x.com"),
        _msg("slack", "c2", "alice", "bug in prod", _ts(0, 9, 10), sender_email="alice@x.com"),
        _msg("teams", "t1", "alice", "meeting at noon", _ts(0, 9, 15)),
        _msg("gmail", "g1", "carol", "check the slack channel", _ts(0, 9, 20)),
    ]
    conversations = engine.correlate_conversations(messages)
    assert conversations  # at least one linked conversation
    assert engine.linked_conversations
    for conv in conversations:
        assert isinstance(conv, LinkedConversation)
        assert conv.unified_messages  # timeline built
        for um in conv.unified_messages:
            assert "_correlation_source" in um
            assert "_correlation_thread" in um
    # participant-based link recorded
    participant_links = [l for l in engine.cross_platform_links
                         if "Shared" in l.reason]
    assert participant_links
    # slack<->teams temporal link recorded
    temporal_links = [l for l in engine.cross_platform_links
                      if "Temporal proximity" in l.reason]
    assert temporal_links
    assert any(isinstance(l, CrossPlatformLink) for l in engine.cross_platform_links)


def test_correlate_no_messages(engine):
    assert engine.correlate_conversations([]) == []


# ============================================================================
# _group_by_thread / _extract_thread_metadata
# ============================================================================

def test_group_by_thread_fallbacks(engine):
    grouped = engine._group_by_thread([
        {"platform": "slack", "thread_id": "t1", "timestamp": _ts()},
        {"platform": "teams", "conversation_id": "t2", "timestamp": _ts()},
        {"platform": "gmail", "timestamp": _ts()},  # no thread -> no_thread
        {"platform": None, "timestamp": _ts()},     # unknown platform
    ])
    assert ("slack", "t1") in grouped
    assert ("teams", "t2") in grouped
    assert ("gmail", "no_thread") in grouped
    assert (None, "no_thread") in grouped  # explicit None platform key passes through


def test_extract_thread_metadata_full(engine):
    messages = [
        _msg("slack", "t1", "alice", "hello", _ts(0, 9), mentions=["bob"]),
        _msg("slack", "t1", "bob", "hi", _ts(0, 9, 5), sender_email="bob@x.com"),
    ]
    metadata = engine._extract_thread_metadata(engine._group_by_thread(messages))
    meta = metadata[("slack", "t1")]
    assert meta["participants"] == {"alice", "bob"}
    assert meta["participant_emails"] == {"bob@x.com"}
    assert meta["message_count"] == 2
    assert meta["start_time"] is not None
    assert meta["end_time"] is not None
    assert meta["thread_id"] == "t1"


def test_extract_thread_metadata_empty_and_no_thread_id(engine):
    metadata = engine._extract_thread_metadata({("slack", "t1"): []})
    assert metadata == {}
    messages = [{"platform": "slack", "id": "msg-1", "content": "x", "timestamp": _ts()}]
    meta = engine._extract_thread_metadata(engine._group_by_thread(messages))
    assert meta[("slack", "no_thread")]["thread_id"] == "msg-1"


def test_extract_thread_metadata_bad_timestamps(engine):
    messages = [
        {"platform": "slack", "thread_id": "t1", "sender": "alice", "content": "x",
         "timestamp": "not-a-date"},
    ]
    meta = engine._extract_thread_metadata(engine._group_by_thread(messages))
    assert meta[("slack", "t1")]["start_time"] is None
    assert meta[("slack", "t1")]["end_time"] is None


# ============================================================================
# _correlate_by_participants
# ============================================================================

def test_correlate_by_participants_strong_and_email_crossmatch(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": {"alice", "bob"}, "participant_emails": {"alice@x.com"},
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": {"alice", "bob", "carol"}, "participant_emails": set(),
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
        ("gmail", "c"): {
            "platform": "gmail", "thread_id": "c", "message_count": 1,
            "participants": {"dan"}, "participant_emails": {"dave@x.com"},
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
    }
    conversations = engine._correlate_by_participants(thread_metadata)
    assert len(conversations) == 1  # slack+teams linked, gmail unlinked
    conv = conversations[0]
    assert conv.correlation_strength == CorrelationStrength.MODERATE  # 2 threads
    assert conv.platforms == {"slack", "teams"}
    assert conv.message_count == 2
    # 2 shared names -> the cross-platform link itself is STRONG
    assert engine.cross_platform_links[0].strength == CorrelationStrength.STRONG
    # gmail stays independent -> no second conversation


def test_correlate_by_participants_email_name_crossmatch(engine):
    """alice@x.com in one thread matches participant 'alice smith' in the other."""
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": {"someone"}, "participant_emails": {"alice@x.com"},
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": {"Alice Smith"}, "participant_emails": set(),
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
    }
    conversations = engine._correlate_by_participants(thread_metadata)
    assert len(conversations) == 1
    assert conversations[0].correlation_strength == CorrelationStrength.MODERATE
    assert "alice@x.com" in conversations[0].participant_emails


def test_correlate_by_participants_single_thread(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": {"alice"}, "participant_emails": set(),
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
    }
    assert engine._correlate_by_participants(thread_metadata) == []


# ============================================================================
# _correlate_by_time
# ============================================================================

def test_correlate_by_time_overlap(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": {"alice"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 0),
            "end_time": datetime(2026, 8, 13, 10, 0),
            "keywords": set(), "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": {"bob"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 10, 30),
            "end_time": datetime(2026, 8, 13, 11, 0),
            "keywords": set(), "messages": [],
        },
        ("gmail", "c"): {
            "platform": "gmail", "thread_id": "c", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": None, "end_time": None,  # no timestamps -> skipped
            "keywords": set(), "messages": [],
        },
    }
    conversations = engine._correlate_by_time(thread_metadata)
    assert len(conversations) == 1
    assert conversations[0].correlation_strength == CorrelationStrength.WEAK
    assert "90 minutes apart" in engine.cross_platform_links[0].reason
    assert engine.cross_platform_links[0].temporal_distance == 5400.0


def test_correlate_by_time_no_overlap(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 0),
            "end_time": datetime(2026, 8, 13, 9, 30),
            "keywords": set(), "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": datetime(2026, 8, 14, 9, 0),
            "end_time": datetime(2026, 8, 14, 9, 30),
            "keywords": set(), "messages": [],
        },
    }
    assert engine._correlate_by_time(thread_metadata) == []


def test_correlate_by_time_self_within_window(engine):
    """meta1 within 2h window of meta2 but processed-skip prevents double-linking."""
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 0),
            "end_time": datetime(2026, 8, 13, 10, 0),
            "keywords": set(), "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 5),
            "end_time": datetime(2026, 8, 13, 9, 10),
            "keywords": set(), "messages": [],
        },
    }
    conversations = engine._correlate_by_time(thread_metadata)
    assert len(conversations) == 1


# ============================================================================
# _correlate_by_content
# ============================================================================

def test_correlate_by_content_match_and_empty_keywords(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug", "release"}, "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug", "deploy"}, "messages": [],
        },
        ("gmail", "c"): {
            "platform": "gmail", "thread_id": "c", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": set(), "messages": [],  # empty keywords -> skipped
        },
    }
    conversations = engine._correlate_by_content(thread_metadata)
    assert len(conversations) == 1
    # overlap {bug} / union {bug, release, deploy} = 1/3 >= 0.3 threshold
    assert engine.cross_platform_links[0].strength == CorrelationStrength.WEAK
    assert "Content similarity" in engine.cross_platform_links[0].reason


def test_correlate_by_content_strong_similarity(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug", "release"}, "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug", "release", "deploy"}, "messages": [],
        },
    }
    conversations = engine._correlate_by_content(thread_metadata)
    assert len(conversations) == 1
    # 2/3 similarity > 0.5 -> MODERATE
    assert engine.cross_platform_links[0].strength == CorrelationStrength.MODERATE


def test_correlate_by_content_below_threshold(engine):
    thread_metadata = {
        ("slack", "a"): {
            "platform": "slack", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug", "release", "deploy", "urgent"}, "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"approval"}, "messages": [],
        },
    }
    assert engine._correlate_by_content(thread_metadata) == []


def test_correlate_by_content_unknown_platform_skipped(engine):
    thread_metadata = {
        ("unknown", "a"): {
            "platform": "unknown", "thread_id": "a", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug"}, "messages": [],
        },
        ("teams", "b"): {
            "platform": "teams", "thread_id": "b", "message_count": 1,
            "participants": set(), "participant_emails": set(),
            "start_time": None, "end_time": None,
            "keywords": {"bug"}, "messages": [],
        },
    }
    assert engine._correlate_by_content(thread_metadata) == []


# ============================================================================
# _correlate_by_references
# ============================================================================

def test_correlate_by_references_within_hour(engine):
    thread_metadata = {
        ("gmail", "g1"): {
            "platform": "gmail", "thread_id": "g1", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 0),
            "end_time": None, "keywords": set(),
            "messages": [{"content": "let's continue on the slack channel"}],
        },
        ("slack", "s1"): {
            "platform": "slack", "thread_id": "s1", "message_count": 1,
            "participants": {"carol", "dave"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 30),
            "end_time": None, "keywords": set(), "messages": [],
        },
    }
    conversations = engine._correlate_by_references(thread_metadata)
    assert len(conversations) == 1
    assert conversations[0].platforms == {"gmail", "slack"}
    assert conversations[0].correlation_strength == CorrelationStrength.MODERATE


def test_correlate_by_references_outside_hour_or_no_times(engine):
    thread_metadata = {
        ("gmail", "g1"): {
            "platform": "gmail", "thread_id": "g1", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 9, 0),
            "end_time": None, "keywords": set(),
            "messages": [{"content": "see you on the slack channel"}],
        },
        ("slack", "s1"): {
            "platform": "slack", "thread_id": "s1", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": datetime(2026, 8, 13, 12, 0),  # 3h away
            "end_time": None, "keywords": set(), "messages": [],
        },
    }
    assert engine._correlate_by_references(thread_metadata) == []


def test_correlate_by_references_no_timestamps(engine):
    thread_metadata = {
        ("gmail", "g1"): {
            "platform": "gmail", "thread_id": "g1", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": None, "end_time": None, "keywords": set(),
            "messages": [{"content": "lets talk on slack"}],
        },
        ("slack", "s1"): {
            "platform": "slack", "thread_id": "s1", "message_count": 1,
            "participants": {"carol"}, "participant_emails": set(),
            "start_time": None, "end_time": None, "keywords": set(), "messages": [],
        },
    }
    assert engine._correlate_by_references(thread_metadata) == []


# ============================================================================
# _merge_correlations
# ============================================================================

def test_merge_correlations_empty(engine):
    assert engine._merge_correlations([], {}) == []


def test_merge_correlations_overlap_and_disjoint(engine):
    conv_a = LinkedConversation(
        conversation_id="a", threads={"slack": "t1", "teams": "t2"},
        platforms={"slack", "teams"}, participants={"alice"},
        topic_keywords={"bug"},
    )
    conv_b = LinkedConversation(
        conversation_id="b", threads={"teams": "t2", "gmail": "g1"},
        platforms={"teams", "gmail"}, participants={"bob"},
        topic_keywords={"release"},
    )
    conv_c = LinkedConversation(
        conversation_id="c", threads={"outlook": "o1"},
        platforms={"outlook"}, participants={"carol"},
        topic_keywords=set(),
    )
    thread_messages = {
        ("slack", "t1"): [{"participant_emails": {"a@x.com"}, "message_count": 2}],
        ("teams", "t2"): [{"message_count": 1}],
        ("gmail", "g1"): [],
        ("outlook", "o1"): [{"message_count": 5}],
    }
    merged = engine._merge_correlations([conv_a, conv_b, conv_c], thread_messages)
    assert len(merged) == 2
    merged_by_id = {c.conversation_id: c for c in merged}
    big = merged_by_id["conv_merged_0"]
    assert big.threads == {"slack": "t1", "teams": "t2", "gmail": "g1"}
    assert big.platforms == {"slack", "teams", "gmail"}
    assert big.participants == {"alice", "bob"}
    assert big.topic_keywords == {"bug", "release"}
    assert big.message_count == 3  # slack 2 + teams 1 (gmail has no messages)
    assert big.participant_emails == {"a@x.com"}
    assert big.correlation_strength == CorrelationStrength.STRONG  # 3 platforms > 2
    assert merged_by_id["conv_merged_1"].threads == {"outlook": "o1"}
    assert merged_by_id["conv_merged_1"].message_count == 5


# ============================================================================
# get_unified_timeline / _build_unified_timeline
# ============================================================================

def test_get_unified_timeline_hit_and_miss(engine):
    engine.linked_conversations["c1"] = LinkedConversation(
        conversation_id="c1", threads={"slack": "t1"}, platforms={"slack"},
        participants=set(), unified_messages=[{"id": "m1"}],
    )
    assert engine.get_unified_timeline("c1") == [{"id": "m1"}]
    assert engine.get_unified_timeline("missing") is None


def test_build_unified_timeline_sorts(engine):
    thread_messages = {
        ("slack", "t1"): [
            {"id": "m1", "timestamp": _ts(0, 10)},
            {"id": "m2", "timestamp": _ts(0, 9)},
        ],
        ("teams", "t2"): [
            {"id": "m3", "timestamp": _ts(0, 11)},
            {"id": "m4"},  # no timestamp -> datetime.min sorts first
        ],
    }
    timeline = engine._build_unified_timeline(
        {"slack": "t1", "teams": "t2", "gmail": "absent"}, thread_messages
    )
    assert [m["id"] for m in timeline] == ["m4", "m2", "m1", "m3"]
    assert timeline[0]["_correlation_source"] == "teams"
    assert timeline[0]["_correlation_thread"] == "t2"


# ============================================================================
# _extract_keywords / _parse_timestamp
# ============================================================================

def test_extract_keywords(engine):
    messages = [
        {"content": "URGENT: the release is blocked"},
        {"content": "review the deployment"},
        {"content": "tiny"},
        {"content": "no important words here"},
    ]
    keywords = engine._extract_keywords(messages)
    assert "urgent" in keywords
    assert "release" in keywords
    assert "blocked" in keywords
    assert "review" in keywords
    assert "tiny" not in keywords  # < 3 chars


def test_parse_timestamp_branches(engine):
    aware = datetime(2026, 8, 13, 10, 0, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 8, 13, 10, 0, 0)
    assert engine._parse_timestamp(None) is None
    assert engine._parse_timestamp(aware) is aware
    assert engine._parse_timestamp(naive) is naive
    assert engine._parse_timestamp("2026-08-13T10:00:00") == naive
    assert engine._parse_timestamp("garbage") is None
    assert engine._parse_timestamp(12345) is None


def test_singleton_helper():
    engine = get_cross_platform_correlation_engine()
    assert isinstance(engine, CrossPlatformCorrelationEngine)
    assert engine is get_cross_platform_correlation_engine()
