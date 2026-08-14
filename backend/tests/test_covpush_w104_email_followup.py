# -*- coding: utf-8 -*-
"""Coverage wave 104 — core/email_followup_engine.py.

Unit coverage of the follow-up candidate detector:
- candidate generation: threshold logic, str/naive/aware sent_at parsing,
  reply suppression by thread_id + received_at ordering.
- REAL BUGS FOUND (TDD RED -> GREEN):
  W104-4: timezone-AWARE sent_at (e.g. ISO strings with +00:00) crashed
          detect_missing_replies with TypeError (naive `now - aware`).
  W104-5: a received message WITHOUT a received_at key crashed the whole
          loop with TypeError (None > datetime) — one bad row killed all
          follow-up detection.

No LLM spend, no network.
"""
import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.email_followup_engine import EmailFollowUpEngine, FollowUpCandidate


@pytest.fixture()
def engine():
    return EmailFollowUpEngine(days_threshold=3)


def _run(*args):
    return asyncio.run(args[0])


NOW = datetime(2026, 8, 13, 12, 0, 0)


def _sent(**kw):
    base = {
        "id": "m1",
        "to": "alice@example.com",
        "subject": "Q3 Plan",
        "sent_at": NOW - timedelta(days=5),
        "thread_id": "thr-1",
        "snippet": "please review",
    }
    base.update(kw)
    return base


class TestDetectMissingReplies:
    def test_empty_inputs(self, engine):
        assert _run(engine.detect_missing_replies([], [])) == []

    def test_recent_message_below_threshold(self, engine):
        msg = _sent(sent_at=NOW - timedelta(days=2))
        assert _run(engine.detect_missing_replies([msg], [])) == []

    def test_message_at_exact_threshold(self, engine):
        msg = _sent(sent_at=NOW - timedelta(days=3))
        assert len(_run(engine.detect_missing_replies([msg], []))) == 1

    def test_candidate_fields(self, engine):
        msg = _sent()
        (cand,) = _run(engine.detect_missing_replies([msg], []))
        assert isinstance(cand, FollowUpCandidate)
        assert cand.id == "m1"
        assert cand.recipient == "alice@example.com"
        assert cand.subject == "Q3 Plan"
        assert cand.days_since_sent == 5
        assert cand.thread_id == "thr-1"
        assert cand.last_message_snippet == "please review"
        assert cand.original_sent_at == msg["sent_at"]

    def test_string_sent_at_parsed(self, engine):
        msg = _sent(sent_at=(NOW - timedelta(days=7)).isoformat())
        (cand,) = _run(engine.detect_missing_replies([msg], []))
        assert cand.days_since_sent == 7

    def test_reply_suppresses_candidate(self, engine):
        msg = _sent()
        reply = {
            "thread_id": "thr-1",
            "received_at": NOW - timedelta(days=1),
            "from": "alice@example.com",
        }
        assert _run(engine.detect_missing_replies([msg], [reply])) == []

    def test_reply_before_sent_does_not_suppress(self, engine):
        msg = _sent()
        early = {"thread_id": "thr-1", "received_at": NOW - timedelta(days=10)}
        assert len(_run(engine.detect_missing_replies([msg], [early]))) == 1

    def test_reply_on_different_thread_does_not_suppress(self, engine):
        msg = _sent()
        other = {"thread_id": "other", "received_at": NOW - timedelta(days=1)}
        assert len(_run(engine.detect_missing_replies([msg], [other]))) == 1

    def test_string_received_at_compared(self, engine):
        msg = _sent()
        reply = {
            "thread_id": "thr-1",
            "received_at": (NOW - timedelta(days=1)).isoformat(),
        }
        assert _run(engine.detect_missing_replies([msg], [reply])) == []

    def test_defaults_when_keys_missing(self, engine):
        msg = {"sent_at": NOW - timedelta(days=4)}
        (cand,) = _run(engine.detect_missing_replies([msg], []))
        assert cand.id == "unknown"
        assert cand.recipient == "unknown"
        assert cand.subject == "No Subject"
        assert cand.thread_id is None
        assert cand.last_message_snippet == ""

    def test_sent_at_missing_uses_now(self, engine):
        msg = _sent()
        del msg["sent_at"]
        assert _run(engine.detect_missing_replies([msg], [])) == []

    def test_multiple_sent_multiple_candidates(self, engine):
        m1 = _sent(id="a", thread_id="t1")
        m2 = _sent(id="b", thread_id="t2", sent_at=NOW - timedelta(days=9))
        reply = {"thread_id": "t2", "received_at": NOW - timedelta(days=1)}
        cands = _run(engine.detect_missing_replies([m1, m2], [reply]))
        assert [c.id for c in cands] == ["a"]

    def test_default_threshold_is_3(self):
        assert EmailFollowUpEngine().days_threshold == 3

    # ---- W104-4: timezone-aware sent_at must not crash ----
    def test_aware_iso_sent_at(self, engine):
        aware = (NOW - timedelta(days=6)).replace(tzinfo=timezone.utc)
        msg = _sent(sent_at=aware.isoformat())
        (cand,) = _run(engine.detect_missing_replies([msg], []))
        assert cand.days_since_sent == 6

    def test_aware_datetime_sent_at(self, engine):
        aware = (NOW - timedelta(days=4)).replace(tzinfo=timezone.utc)
        msg = _sent(sent_at=aware)
        (cand,) = _run(engine.detect_missing_replies([msg], []))
        assert cand.days_since_sent == 4

    def test_aware_sent_with_aware_reply(self, engine):
        sent = (NOW - timedelta(days=5)).replace(tzinfo=timezone.utc)
        reply_ts = (NOW - timedelta(days=1)).replace(tzinfo=timezone.utc)
        msg = _sent(sent_at=sent)
        reply = {"thread_id": "thr-1", "received_at": reply_ts}
        assert _run(engine.detect_missing_replies([msg], [reply])) == []

    # ---- W104-5: received message without received_at must not crash ----
    def test_received_without_received_at(self, engine):
        msg = _sent()
        reply = {"thread_id": "thr-1"}
        (cand,) = _run(engine.detect_missing_replies([msg], [reply]))
        assert cand.id == "m1"
