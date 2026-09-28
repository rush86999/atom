"""Tests for decision automation: ledger, resolve, status, act-rules (Phase 5).

Contract:
- Nothing enforces by default. resolve_decision_enforce() is False unless
  the env hard-switch wins or a ledger row was explicitly approved/applied.
- Revocation always wins (fail-safe), regardless of mode.
- status() never raises and reports off/collecting/ready/enforced honestly.
- Act-rules are pure threshold functions; no prod path acts on them yet.
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch


def _auto():
    from core import decision_automation as da
    import importlib
    importlib.reload(da)
    return da


def _session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from core.models import Base
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestActRules:
    def test_intent_act_rule(self):
        da = _auto()
        assert da.intent_should_act("workflow", 0.82, 0.6) is True
        assert da.intent_should_act("workflow", 0.53, 0.6) is False
        assert da.intent_should_act(None, 0.9, 0.6) is False
        assert da.intent_should_act("chat", 0.6, 0.6) is True  # boundary acts

    def test_gate_block_rule(self):
        da = _auto()
        assert da.gate_should_block("block", 0.95, 0.9) is True
        assert da.gate_should_block("block", 0.14, 0.9) is False
        assert da.gate_should_block("allow", 0.99, 0.9) is False
        assert da.gate_should_block(None, 0.99, 0.9) is False

    def test_turn_skip_rule(self):
        da = _auto()
        assert da.turn_should_skip_extraction(0.1, 0.2) is True
        assert da.turn_should_skip_extraction(0.5, 0.2) is False
        assert da.turn_should_skip_extraction(None, 0.2) is False


class TestResolve:
    def test_default_off(self):
        da = _auto()
        with patch.object(da, "_auto_enforce_mode", return_value="off"):
            assert da.resolve_decision_enforce(_session(), "intent") is False

    def test_env_hard_switch_wins(self):
        da = _auto()
        with patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch.object(da, "_force_enforce", return_value=True):
            assert da.resolve_decision_enforce(_session(), "intent") is True

    def test_applied_ledger_enforces(self):
        da = _auto()
        session = _session()
        da._write_action(session, "intent", "certify", "approve", {"n": 40})
        act = da._latest_action(session, "intent")
        da.approve_action(session, act.id)
        with patch.object(da, "_auto_enforce_mode", return_value="approve"), \
             patch.object(da, "_force_enforce", return_value=False):
            assert da.resolve_decision_enforce(session, "intent") is True

    def test_revocation_always_wins(self):
        da = _auto()
        session = _session()
        da._write_action(session, "intent", "certify", "auto", {"n": 40})
        act = da._latest_action(session, "intent")
        da.approve_action(session, act.id)
        da._write_action(session, "intent", "revoke", "auto", {"reason": "regression"})
        rev = da._latest_action(session, "intent")
        da.approve_action(session, rev.id)
        with patch.object(da, "_auto_enforce_mode", return_value="auto"), \
             patch.object(da, "_force_enforce", return_value=True):
            # env hard-switch still wins (operator kill-switch), but an
            # applied revoke beats an applied certify:
            assert da.resolve_decision_enforce(session, "intent") is True
        with patch.object(da, "_auto_enforce_mode", return_value="auto"), \
             patch.object(da, "_force_enforce", return_value=False):
            assert da.resolve_decision_enforce(session, "intent") is False

    def test_reject_never_enforces(self):
        da = _auto()
        session = _session()
        da._write_action(session, "intent", "certify", "approve", {"n": 40})
        act = da._latest_action(session, "intent")
        da.reject_action(session, act.id)
        with patch.object(da, "_auto_enforce_mode", return_value="approve"), \
             patch.object(da, "_force_enforce", return_value=False):
            assert da.resolve_decision_enforce(session, "intent") is False


class TestStatus:
    def test_off_when_master_disabled(self):
        da = _auto()
        with patch("core.decision_service.ollaya_enabled", return_value=False):
            st = da.decision_status(_session())
            assert st["phase"] == "off"
            assert "ATOM_OLLAYA_ENABLED" in st["next_action"]

    def test_collecting_with_no_rows(self):
        da = _auto()
        with patch("core.decision_service.ollaya_enabled", return_value=True):
            st = da.decision_status(_session())
            assert st["phase"] == "collecting"
            assert st["surfaces"]["intent"]["rows"] == 0

    def test_never_raises_on_db_error(self):
        da = _auto()
        bad = Mock()
        bad.query.side_effect = RuntimeError("db down")
        with patch("core.decision_service.ollaya_enabled", return_value=True):
            st = da.decision_status(bad)
            assert st["phase"] == "error"


class TestAutomationPass:
    def _seed_intent_rows(self, session, n, agree_every=1):
        from core.models import DecisionRouterAudit
        DecisionRouterAudit.__table__.create(bind=session.get_bind(), checkfirst=True)
        for i in range(n):
            agree = (i % agree_every == 0)
            session.add(DecisionRouterAudit(
                workspace_id="ws", surface="intent", input_hash=f"h{i}",
                llm_category="workflow", llm_confidence=0.9,
                ollaya_choice="workflow" if agree else "chat",
                ollaya_confidence=0.9 if agree else 0.4,
                agreement=agree, ollaya_latency_ms=90.0,
                model="laya", enforced=False))
        session.commit()

    def test_hold_creates_no_action(self):
        da = _auto()
        session = _session()
        self._seed_intent_rows(session, 5)
        with patch.object(da, "_auto_enforce_mode", return_value="approve"):
            actions = da.run_automation_pass(session)
            assert actions == []
            assert da._latest_action(session, "intent") is None

    def test_ready_queues_approval(self):
        da = _auto()
        session = _session()
        self._seed_intent_rows(session, 40, agree_every=1)  # 100% agreement
        with patch.object(da, "_auto_enforce_mode", return_value="approve"):
            actions = da.run_automation_pass(session)
            assert len(actions) == 1
            assert actions[0]["surface"] == "intent"
            assert actions[0]["verdict"] == "certify"
            assert actions[0]["state"] == "approval"

    def test_ready_auto_applies_in_auto_mode(self):
        da = _auto()
        session = _session()
        self._seed_intent_rows(session, 40, agree_every=1)
        with patch.object(da, "_auto_enforce_mode", return_value="auto"):
            actions = da.run_automation_pass(session)
            assert actions[0]["state"] == "applied"
            with patch.object(da, "_force_enforce", return_value=False):
                assert da.resolve_decision_enforce(session, "intent") is True

    def test_regression_auto_revokes(self):
        da = _auto()
        session = _session()
        self._seed_intent_rows(session, 40, agree_every=1)
        with patch.object(da, "_auto_enforce_mode", return_value="auto"):
            da.run_automation_pass(session)  # certify + apply
            assert da.resolve_decision_enforce(session, "intent") is True
        # regime change: wipe, seed failing stats
        from core.models import DecisionRouterAudit
        session.query(DecisionRouterAudit).delete()
        session.commit()
        self._seed_intent_rows(session, 40, agree_every=4)  # 25% agreement
        with patch.object(da, "_auto_enforce_mode", return_value="notify"):
            actions = da.run_automation_pass(session)
            revokes = [a for a in actions if a["verdict"] == "revoke"]
            assert len(revokes) == 1  # automatic even in notify mode
            with patch.object(da, "_force_enforce", return_value=False):
                assert da.resolve_decision_enforce(session, "intent") is False


class TestAutomationLoop:
    @pytest.mark.asyncio
    async def test_ensure_schedules_task(self):
        import asyncio
        da = _auto()
        da._automation_task = None
        with patch.object(da, "_auto_enforce_mode", return_value="approve"):
            da.ensure_automation_task()
            task = da._automation_task
            assert task is not None
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            da._automation_task = None

    @pytest.mark.asyncio
    async def test_ensure_noop_when_off(self):
        da = _auto()
        da._automation_task = None
        with patch.object(da, "_auto_enforce_mode", return_value="off"):
            da.ensure_automation_task()
            assert da._automation_task is None

    @pytest.mark.asyncio
    async def test_ensure_idempotent(self):
        import asyncio
        da = _auto()
        da._automation_task = None
        with patch.object(da, "_auto_enforce_mode", return_value="approve"):
            da.ensure_automation_task()
            first = da._automation_task
            da.ensure_automation_task()
            assert da._automation_task is first
            first.cancel()
            try:
                await first
            except asyncio.CancelledError:
                pass
            da._automation_task = None

    def test_interval_default(self):
        da = _auto()
        with patch("core.runtime_settings.get_float_setting",
                   side_effect=RuntimeError("no settings")):
            assert da.automation_interval_min() == 60.0
