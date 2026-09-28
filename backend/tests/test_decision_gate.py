"""Tests for the sandbox advisory gate (Phase 4b).

Contract:
- Log-only. The sandbox decision is NEVER altered; rows record the
  would-have verdict for future certification.
- Inline-safe: tight timeout, truncated state, deterministic sampling.
  Timeout/fallback/disabled → None (abstain), never raises.
- No raw args in the DB — args_hash only.
"""

import os
os.environ["TESTING"] = "1"

import hashlib
import json
import pytest
from unittest.mock import Mock, patch


def _shadow():
    from core import decision_shadow as sh
    import importlib
    importlib.reload(sh)
    return sh


def _gate_wire(verdict="allow", confidence=0.9, risky=0.1):
    return {"source": "ollaya", "answers": {
        "verdict": {"type": "choice", "choice": verdict, "confidence": confidence,
                    "probabilities": {}},
        "risky": {"type": "noul", "noul": risky}}, "model": "laya",
        "latency_ms": 80.0}


class TestGateQuestions:
    def test_shape(self):
        from core.decision_questions import ACTION_JUDGMENTS, GATE_TIMEOUT_S
        assert set(ACTION_JUDGMENTS) == {"verdict", "risky"}
        assert ACTION_JUDGMENTS["verdict"]["type"] == "choice"
        assert set(ACTION_JUDGMENTS["verdict"]["criteria"]) == {"allow", "ask", "block"}
        assert ACTION_JUDGMENTS["risky"]["type"] == "noul"
        assert GATE_TIMEOUT_S <= 1.0


class TestGateSampling:
    def test_deterministic(self):
        sh = _shadow()
        a = [sh._gate_sampled("read_file", "abc123", 0.1) for _ in range(3)]
        assert a[0] == a[1] == a[2]

    def test_zero_rate_never_samples(self):
        sh = _shadow()
        assert sh._gate_sampled("x", "y", 0.0) is False

    def test_full_rate_always_samples(self):
        sh = _shadow()
        assert sh._gate_sampled("x", "y", 1.0) is True


class TestGateRecordBuilder:
    def test_agreement(self):
        sh = _shadow()
        rec = sh.build_gate_audit_record(
            "read_file", "abc123", "allowed", _gate_wire("allow", 0.9, 0.1))
        assert rec["ollaya_verdict"] == "allow"
        assert rec["agreement"] is True
        assert rec["sandbox_decision"] == "allowed"

    def test_divergence_recorded(self):
        sh = _shadow()
        rec = sh.build_gate_audit_record(
            "delete_db", "def456", "allowed", _gate_wire("block", 0.85, 0.95))
        assert rec["ollaya_verdict"] == "block"
        assert rec["agreement"] is False

    def test_fallback_abstains(self):
        sh = _shadow()
        rec = sh.build_gate_audit_record(
            "x", "y", "allowed",
            {"source": "fallback", "answers": {}, "model": "l", "latency_ms": 1.0})
        assert rec["ollaya_verdict"] is None
        assert rec["agreement"] is False

    def test_no_raw_args(self):
        sh = _shadow()
        rec = sh.build_gate_audit_record(
            "send_email", "h", "allowed",
            _gate_wire(), args={"to": "secret@example.com"})
        assert "secret@example.com" not in str(rec)


class TestObserveGate:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def test_disabled_returns_none(self):
        sh = _shadow()
        with patch.object(sh, "shadow_enabled_gate", return_value=False), \
             patch("core.decision_shadow._decide", side_effect=AssertionError("no call")):
            assert sh.observe_gate(self._session(), "ws", "tool", {}, "allowed", {}) is None

    def test_persists_row(self):
        sh = _shadow()
        session = self._session()
        with patch.object(sh, "shadow_enabled_gate", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch.object(sh, "_gate_sampled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=_gate_wire("ask", 0.7, 0.6)):
            rec = sh.observe_gate(session, "ws1", "send_email",
                                  {"to": "a@b.c"}, "allowed",
                                  {"tier": "supervised"})
            assert rec is not None and rec["ollaya_verdict"] == "ask"
        from core.models import DecisionGateAudit
        rows = session.query(DecisionGateAudit).all()
        assert len(rows) == 1
        assert rows[0].enforced is False
        assert rows[0].args_hash is not None

    def test_not_sampled_returns_none(self):
        sh = _shadow()
        with patch.object(sh, "shadow_enabled_gate", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch.object(sh, "_gate_sampled", return_value=False), \
             patch("core.decision_shadow._decide", side_effect=AssertionError("no call")):
            assert sh.observe_gate(self._session(), "ws", "t", {}, "allowed", {}) is None

    def test_db_error_never_raises(self):
        sh = _shadow()
        bad = Mock()
        bad.add.side_effect = RuntimeError("db down")
        with patch.object(sh, "shadow_enabled_gate", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch.object(sh, "_gate_sampled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=_gate_wire()):
            assert sh.observe_gate(bad, "ws", "t", {}, "allowed", {}) is None

    def test_backfills_surface_on_legacy_table(self):
        """Tables created before the surface column get it via ALTER."""
        sh = _shadow()
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        from core.models import Base, DecisionGateAudit
        engine = create_engine("sqlite:///:memory:")
        DecisionGateAudit.__table__.create(bind=engine, checkfirst=True)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE decision_gate_audit DROP COLUMN surface"))
        session = sessionmaker(bind=engine)()
        with patch.object(sh, "shadow_enabled_gate", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch.object(sh, "_gate_sampled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=_gate_wire("allow", 0.9, 0.1)):
            rec = sh.observe_gate(session, "ws1", "read_file", {"p": 1},
                                  "allowed", {"tier": "supervised"})
            assert rec is not None
        from core.models import DecisionGateAudit
        row = session.query(DecisionGateAudit).one()
        assert row.surface == "gate"
        nulls = session.execute(
            text("SELECT COUNT(*) FROM decision_gate_audit WHERE surface IS NULL")
        ).scalar()
        assert nulls == 0
