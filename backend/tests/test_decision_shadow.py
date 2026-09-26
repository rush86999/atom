"""Tests for the intent-routing shadow hook (Phase 2).

Contract:
- Shadow NEVER changes the classification result and NEVER raises.
- Opt-in via ATOM_OLLAYA_SHADOW_INTENT (default off); requires ATOM_OLLAYA_ENABLED.
- Audit rows store an input hash, never raw request text (PHI hygiene).
- DB errors, ollaya fallback, disabled flags → record skipped (None), no raise.
"""

import os
os.environ["TESTING"] = "1"

import hashlib
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch


def _shadow():
    from core import decision_shadow as sh
    import importlib
    importlib.reload(sh)
    return sh


class TestQuestionSet:
    def test_maps_all_intent_categories(self):
        from core.decision_questions import INTENT_ROUTING_QUESTIONS, INTENT_CHOICE_TO_CATEGORY
        q = INTENT_ROUTING_QUESTIONS["intent"]
        assert q["type"] == "choice"
        assert set(q["criteria"]) == {"chat", "workflow", "task"}
        assert set(INTENT_CHOICE_TO_CATEGORY.values()) == {"chat", "workflow", "task"}


class TestRecordBuilder:
    def test_agreement_when_choices_match(self):
        sh = _shadow()
        rec = sh.build_intent_audit_record(
            "Explain maturity", llm_category="chat", llm_confidence=0.9,
            decide_result={"source": "ollaya", "answers": {
                "intent": {"type": "choice", "choice": "chat", "confidence": 0.95,
                           "probabilities": {}}}, "model": "laya", "latency_ms": 10.0},
        )
        assert rec["agreement"] is True
        assert rec["ollaya_choice"] == "chat"
        assert rec["llm_category"] == "chat"

    def test_disagreement_recorded_not_hidden(self):
        sh = _shadow()
        rec = sh.build_intent_audit_record(
            "Run the report", llm_category="workflow", llm_confidence=0.8,
            decide_result={"source": "ollaya", "answers": {
                "intent": {"type": "choice", "choice": "task", "confidence": 0.7,
                           "probabilities": {}}}, "model": "laya", "latency_ms": 10.0},
        )
        assert rec["agreement"] is False
        assert rec["ollaya_choice"] == "task"

    def test_fallback_produces_no_choice(self):
        sh = _shadow()
        rec = sh.build_intent_audit_record(
            "hi", llm_category="chat", llm_confidence=0.9,
            decide_result={"source": "fallback", "answers": {}, "model": "laya",
                           "latency_ms": 5.0},
        )
        assert rec["ollaya_choice"] is None
        assert rec["agreement"] is False

    def test_no_raw_text_stored(self):
        sh = _shadow()
        secret = "patient John Doe SSN 123"
        rec = sh.build_intent_audit_record(
            secret, llm_category="chat", llm_confidence=0.9,
            decide_result={"source": "fallback", "answers": {}, "model": "laya",
                           "latency_ms": 1.0},
        )
        blob = str(rec)
        assert "John Doe" not in blob and "123" not in blob
        assert rec["input_hash"] == hashlib.sha256(" ".join(secret.lower().split()).encode()).hexdigest()


class TestRecordShadow:
    def _session(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from core.models import Base
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        return sessionmaker(bind=engine)()

    def test_disabled_skips_without_http(self):
        sh = _shadow()
        session = self._session()
        with patch.object(sh, "shadow_enabled", return_value=False), \
             patch("core.decision_shadow._decide", side_effect=AssertionError("no call")):
            assert sh.record_intent_shadow(session, "ws", "hello", "chat", 0.9) is None

    def test_persists_audit_row(self):
        sh = _shadow()
        session = self._session()
        wire = {"source": "ollaya", "answers": {
            "intent": {"type": "choice", "choice": "chat", "confidence": 0.9,
                       "probabilities": {}}}, "model": "laya", "latency_ms": 10.0}
        with patch.object(sh, "shadow_enabled", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=wire):
            rec = sh.record_intent_shadow(session, "ws1", "hello there", "chat", 0.9)
            assert rec is not None and rec["agreement"] is True
        from core.models import DecisionRouterAudit
        rows = session.query(DecisionRouterAudit).all()
        assert len(rows) == 1
        assert rows[0].workspace_id == "ws1"
        assert rows[0].enforced is False

    def test_db_error_never_raises(self):
        sh = _shadow()
        bad_session = Mock()
        bad_session.add.side_effect = RuntimeError("db down")
        wire = {"source": "ollaya", "answers": {
            "intent": {"type": "choice", "choice": "chat", "confidence": 0.9,
                       "probabilities": {}}}, "model": "laya", "latency_ms": 1.0}
        with patch.object(sh, "shadow_enabled", return_value=True), \
             patch("core.decision_service.ollaya_enabled", return_value=True), \
             patch("core.decision_shadow._decide", return_value=wire):
            assert sh.record_intent_shadow(bad_session, "ws", "hi", "chat", 0.9) is None


class TestClassifyWiring:
    def _chat_llm(self):
        mock_llm = Mock()
        mock_llm.generate_completion = AsyncMock(return_value={"content": json.dumps({
            "category": "chat", "confidence": 0.95, "reasoning": "simple",
            "is_structured": False, "is_long_horizon": False,
            "requires_agent_recruitment": False, "blueprint_applicable": False})})
        return mock_llm

    @pytest.mark.asyncio
    async def test_classify_result_unchanged_with_shadow(self):
        import asyncio
        from core.intent_classifier import IntentClassifier
        with patch("core.intent_classifier.get_llm_service"):
            classifier = IntentClassifier(db=Mock(), workspace_id="ws-shadow")
        classifier.llm = self._chat_llm()
        with patch("core.decision_shadow.record_intent_shadow",
                   return_value={"agreement": True}) as rec:
            result = await classifier.classify_intent("Explain agent maturity")
            await asyncio.sleep(0.3)
            assert result.category.value == "chat"
            assert result.suggested_handler == "llm_service"
            assert rec.called
            args = rec.call_args[0]
            assert args[0] is None and args[1] == "ws-shadow"
            assert args[3] == "chat" and args[4] == pytest.approx(0.95)

    @pytest.mark.asyncio
    async def test_classify_survives_shadow_failure(self):
        from core.intent_classifier import IntentClassifier
        with patch("core.intent_classifier.get_llm_service"):
            classifier = IntentClassifier(db=Mock(), workspace_id="ws-shadow")
        classifier.llm = self._chat_llm()
        with patch("core.decision_shadow.schedule_intent_shadow",
                   side_effect=RuntimeError("shadow down")):
            result = await classifier.classify_intent("Explain agent maturity")
            assert result.category.value == "chat"


class TestNluBridge:
    def test_mapping_table(self):
        from core.decision_shadow import NLU_TO_INTENT
        assert NLU_TO_INTENT == {"knowledge_query": "chat",
                                 "recurring_automation": "workflow"}

    def test_mapped_category_delegates(self):
        sh = _shadow()
        with patch.object(sh, "schedule_intent_shadow") as sched:
            sh.schedule_nlu_shadow("ws", "do I have meetings?", "knowledge_query", 0.9)
            sched.assert_called_once()
            assert sched.call_args[0][2] == "chat"

    def test_unmapped_category_never_fabricates(self):
        sh = _shadow()
        with patch.object(sh, "schedule_intent_shadow") as sched:
            sh.schedule_nlu_shadow("ws", "do the thing", "one_off", 0.7)
            assert sched.call_args[0][2] == "nlu:one_off"

    def test_unmapped_records_disagreement(self):
        sh = _shadow()
        rec = sh.build_intent_audit_record(
            "do the thing", llm_category="nlu:one_off", llm_confidence=0.7,
            decide_result={"source": "ollaya", "answers": {
                "intent": {"type": "choice", "choice": "task", "confidence": 0.6,
                           "probabilities": {}}}, "model": "laya", "latency_ms": 5.0})
        assert rec["agreement"] is False
        assert rec["llm_category"] == "nlu:one_off"

    def test_bridge_never_raises(self):
        sh = _shadow()
        with patch.object(sh, "schedule_intent_shadow", side_effect=RuntimeError("x")):
            sh.schedule_nlu_shadow("ws", "hi", None, None)  # must not raise
