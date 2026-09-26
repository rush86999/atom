"""Tests for turn-judgment shadow telemetry (Phase 3).

Contract (mirrors intent shadow):
- Record-only. No consumer reads these rows yet; advisory consumers come
  with their own gates in Phase 4.
- NEVER raises, NEVER blocks. Opt-in via ATOM_OLLAYA_SHADOW_TURN + master.
- Audit stores hashes + probabilities, never raw digest text.
- Digest builder is bounded (TURN_DIGEST_MAX_CHARS).
"""

import os
os.environ["TESTING"] = "1"

import hashlib
import pytest
from unittest.mock import Mock, patch


def _shadow():
    from core import decision_shadow as sh
    import importlib
    importlib.reload(sh)
    return sh


def _judge_wire(**probs):
    answers = {k: {"type": "noul", "noul": v} for k, v in probs.items()}
    return {"source": "ollaya", "answers": answers, "model": "laya",
            "latency_ms": 90.0}


class TestTurnQuestions:
    def test_five_noul_statements(self):
        from core.decision_questions import TURN_JUDGMENTS, TURN_DIGEST_MAX_CHARS
        assert set(TURN_JUDGMENTS) == {"has_durable_fact", "on_task", "task_done",
                                       "pending_question", "stuck"}
        for name, q in TURN_JUDGMENTS.items():
            assert q["type"] == "noul", name
            assert q["instructions"] and q["instructions"].endswith("?"), name
        assert TURN_DIGEST_MAX_CHARS >= 1000


class TestTurnDigest:
    def test_bounded_and_structured(self):
        sh = _shadow()
        steps = [{"thought": "t" * 5000, "output": "o" * 5000} for _ in range(10)]
        digest = sh.build_turn_digest("do the thing", steps, "done it")
        from core.decision_questions import TURN_DIGEST_MAX_CHARS
        assert len(digest) <= TURN_DIGEST_MAX_CHARS
        assert "REQUEST: do the thing" in digest
        assert "FINAL ANSWER: done it" in digest

    def test_empty_steps_ok(self):
        sh = _shadow()
        digest = sh.build_turn_digest("hi", [], "hello")
        assert "REQUEST: hi" in digest and "FINAL ANSWER: hello" in digest


class TestTurnRecordBuilder:
    def test_parses_probabilities(self):
        sh = _shadow()
        rec = sh.build_turn_audit_record(
            "digest", "exec1", "sess1",
            _judge_wire(has_durable_fact=0.9, on_task=0.8, task_done=0.1,
                        pending_question=0.2, stuck=0.05))
        assert rec["judgments"]["has_durable_fact"] == pytest.approx(0.9)
        assert rec["judgments"]["stuck"] == pytest.approx(0.05)
        assert rec["execution_id"] == "exec1"
        assert rec["surface"] == "turn"

    def test_missing_judgment_is_none(self):
        sh = _shadow()
        rec = sh.build_turn_audit_record(
            "digest", None, None, _judge_wire(on_task=0.7))
        assert rec["judgments"]["on_task"] == pytest.approx(0.7)
        assert rec["judgments"]["task_done"] is None

    def test_fallback_empty_judgments(self):
        sh = _shadow()
        rec = sh.build_turn_audit_record(
            "digest", None, None,
            {"source": "fallback", "answers": {}, "model": "laya", "latency_ms": 1.0})
        assert all(v is None for v in rec["judgments"].values())

    def test_no_raw_text_stored(self):
        sh = _shadow()
        secret = "REQUEST: patient John Doe owes $50"
        rec = sh.build_turn_audit_record(secret, None, None, _judge_wire(on_task=0.5))
        assert "John Doe" not in str(rec)
        assert rec["input_hash"] == hashlib.sha256(" ".join(secret.lower().split()).encode()).hexdigest()


class TestRecordTurnShadow:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def test_disabled_skips(self):
        sh = _shadow()
        with patch.object(sh, "shadow_enabled_turn", return_value=False), \
             patch("core.decision_shadow._decide", side_effect=AssertionError("no call")):
            assert sh.record_turn_shadow(self._session(), "ws", "digest", None, None) is None

    def test_persists_row(self):
        sh = _shadow()
        session = self._session()
        with patch.object(sh, "shadow_enabled_turn", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch("core.decision_shadow._decide",
                   return_value=_judge_wire(has_durable_fact=0.9, on_task=0.8,
                                            task_done=0.1, pending_question=0.2,
                                            stuck=0.05)):
            rec = sh.record_turn_shadow(session, "ws1", "digest text", "e1", "s1")
            assert rec is not None
            assert rec["judgments"]["has_durable_fact"] == pytest.approx(0.9)
        from core.models import DecisionTurnAudit
        rows = session.query(DecisionTurnAudit).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == "ws1"
        assert rows[0].judgments["on_task"] == pytest.approx(0.8)
        assert rows[0].enforced is False

    def test_db_error_never_raises(self):
        sh = _shadow()
        bad = Mock()
        bad.add.side_effect = RuntimeError("db down")
        with patch.object(sh, "shadow_enabled_turn", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=_judge_wire(on_task=0.5)):
            assert sh.record_turn_shadow(bad, "ws", "digest", None, None) is None

    def test_schedule_never_raises(self):
        sh = _shadow()
        with patch("core.decision_shadow.record_turn_shadow",
                   side_effect=RuntimeError("boom")):
            sh.schedule_turn_shadow("ws", "digest", None, None)  # must not raise
