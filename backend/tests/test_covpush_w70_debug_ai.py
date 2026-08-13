# -*- coding: utf-8 -*-
"""Coverage wave 70 — core/debug_ai_assistant (in-memory SQLite + patched
generators, zero LLM spend, no network).

- DebugAIAssistant: ask routing through all 6 handlers + outer except,
  _detect_intent (every pattern + fallback), _handle_component_health_question
  (regex match + failing-health branch with recent errors, healthy branch,
  context fallback, clarification, system-health branch via real DebugMonitor,
  exception), _handle_failure_question (clarification, errors + related
  insights + suggestions, no-errors, exception), _handle_performance_question
  (clarification, warning insight, non-warning insight, no-data, exception),
  _handle_consistency_question (clarification, no-activity, insight present,
  insight absent, component-only match — BUG-FIX W70-5 — exception),
  _handle_error_patterns_question (none, aggregated, exception),
  _handle_general_question (operation progress, low/high error-rate status,
  exception), _generate_failure_suggestions, _get_system_recommendations
  (all branches), _error_response.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import (  # noqa: F401 (register models)
    DebugEvent,
    DebugInsight,
)
from core.debug_ai_assistant import DebugAIAssistant


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _event(db, eid, *, component_type="agent", component_id="agent-1",
           correlation_id="corr-1", level="INFO", message="msg",
           data=None, ts=None):
    event = DebugEvent(
        id=eid,
        event_type="log",
        component_type=component_type,
        component_id=component_id,
        correlation_id=correlation_id,
        level=level,
        message=message,
        data=data or {},
        timestamp=ts if ts is not None else datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()
    return event


def _insight(db, iid, *, insight_type="error", severity="warning", title="T",
             summary="S", evidence=None, suggestions=None, generated_at=None,
             resolved=False):
    insight = DebugInsight(
        id=iid,
        insight_type=insight_type,
        severity=severity,
        title=title,
        description="D",
        summary=summary,
        evidence=evidence or {},
        confidence_score=0.9,
        suggestions=suggestions or [],
        scope="component",
        affected_components=[{"type": "agent", "id": "agent-1"}],
        resolved=resolved,
        generated_at=generated_at if generated_at is not None else datetime.now(timezone.utc),
    )
    db.add(insight)
    db.commit()
    return insight


class _BadSession:
    def query(self, model):
        raise RuntimeError("db down")


@pytest.fixture()
def assistant(db):
    return DebugAIAssistant(db_session=db)


# ============================================================================
# ask routing + intent detection
# ============================================================================

class TestAsk:
    async def test_ask_health_intent(self, db, assistant):
        result = await assistant.ask("how is agent-1 health?")
        assert "Which component" in result["answer"] or "score" in str(result.get("answer", ""))

    async def test_ask_failure_intent(self, db, assistant):
        result = await assistant.ask("why is agent-1 failing?")
        assert "clarification_needed" in result or "error" in str(result).lower()

    async def test_ask_performance_intent(self, db, assistant):
        result = await assistant.ask("why is agent-1 slow?")
        assert "No performance data available" in result["answer"]

    async def test_ask_consistency_intent(self, db, assistant):
        # component-only consistency question must yield an answer (W70-5)
        result = await assistant.ask("is agent-1 data consistent?")
        assert result is not None
        assert "operation" in result["answer"].lower()

    async def test_ask_error_patterns_intent(self, db, assistant):
        result = await assistant.ask("show recurring error patterns")
        assert "No significant error patterns" in result["answer"]

    async def test_ask_general_intent(self, db, assistant):
        result = await assistant.ask("what happened with op-777?")
        assert "Operation -777" in result["answer"]

    async def test_ask_outer_exception(self, db):
        # A non-string question raises inside ask() before intent routing —
        # every handler has its own try/except, so this is the only reachable
        # outer-except path.
        bad = DebugAIAssistant(db_session=db)
        result = await bad.ask(None)
        assert result["confidence"] == 0.0
        assert "error" in result["answer"].lower()

    def test_detect_intent_all_patterns(self, db, assistant):
        cases = {
            "how is agent health today": "component_health",
            "why is workflow-1 failing": "failure_analysis",
            "system is slow and latency is high": "performance_analysis",
            "check data consistency across replicas": "consistency_check",
            "recurring error pattern in logs": "error_patterns",
            "explain what happened": "general_explanation",
            "the sky is blue": "general_explanation",
        }
        for question, expected in cases.items():
            assert assistant._detect_intent(question) == expected, question


# ============================================================================
# component health question
# ============================================================================

class TestComponentHealthQuestion:
    async def test_failing_component_with_recent_errors(self, db, assistant):
        # the handler regex extracts the bare id ("agent-123" → "123")
        for i in range(4):
            _event(db, f"ok-{i}", component_id="123", level="INFO")
        for i in range(6):
            _event(db, f"bad-{i}", component_id="123", level="ERROR",
                   message=f"failure {i}")
        result = await assistant._handle_component_health_question(
            "how is agent-123 doing", None)
        assert "is experiencing issues" in result["answer"]
        assert result["confidence"] == 0.90
        assert result["evidence"]["health_score"] == 40
        assert result["evidence"]["error_rate"] == 0.6
        assert len(result["evidence"]["recent_errors"]) == 5  # handler caps at 5
        assert len(result["suggestions"]) == 3

    async def test_healthy_component(self, db, assistant):
        _event(db, "h-1", component_id="agent-5", level="INFO")
        result = await assistant._handle_component_health_question(
            "how is agent-5 health?", None)
        assert "is healthy" in result["answer"]
        assert result["confidence"] == 0.95
        assert result["evidence"]["health_score"] == 100

    async def test_no_component_clarification(self, db, assistant):
        result = await assistant._handle_component_health_question(
            "how is the system health today?", None)
        assert result["clarification_needed"] == "component_id"
        assert result["confidence"] == 0.5

    async def test_context_fallback(self, db, assistant):
        _event(db, "ctx-1", component_id="agent-7", level="INFO")
        result = await assistant._handle_component_health_question(
            "what is the health?",
            {"component_type": "agent", "component_id": "agent-7"})
        assert result["evidence"]["health_score"] == 100

    async def test_system_health_branch(self, db, assistant):
        for i in range(5):
            _event(db, f"sys-bad-{i}", component_id="sys-1", level="ERROR")
        for i in range(5):
            _event(db, f"sys-ok-{i}", component_id="sys-2", level="INFO")
        result = await assistant._handle_component_health_question(
            "how is systemwide health today", None)
        assert "System health score is" in result["answer"]
        assert result["confidence"] == 0.85
        assert "suggestions" in result

    async def test_exception(self, db):
        bad = DebugAIAssistant(db_session=_BadSession())
        with patch.object(bad.query_api, "get_component_health",
                          new=AsyncMock(return_value={
                              "health_score": 0, "error_rate": 1.0,
                              "error_events": 9, "recent_insights": []})):
            with patch.object(bad.logger, "error"):
                result = await bad._handle_component_health_question(
                    "how is agent-1?", None)
        assert result["confidence"] == 0.0
        assert "error" in result["answer"].lower()


# ============================================================================
# failure question
# ============================================================================

class TestFailureQuestion:
    async def test_no_component_clarification(self, db, assistant):
        result = await assistant._handle_failure_question("why is it failing?", None)
        assert result["clarification_needed"] == "component_id"

    async def test_errors_with_related_insights(self, db, assistant):
        _event(db, "f1", component_id="9", level="ERROR", message="timeout")
        _event(db, "f2", component_id="9", level="ERROR", message="timeout")
        _insight(db, "ins-rel", suggestions=["check timeout config", "timeout fix"])
        result = await assistant._handle_failure_question(
            "why is agent-9 failing?", None)
        assert "2 error(s)" in result["answer"]
        assert "timeout (2 occurrences)" in result["answer"]
        assert result["confidence"] == 0.85
        assert result["evidence"]["common_errors"]["timeout"] == 2
        assert len(result["related_insights"]) == 1
        assert "check timeout config" in result["suggestions"]

    async def test_no_errors(self, db, assistant):
        result = await assistant._handle_failure_question(
            "why is agent-77 failing?", None)
        assert "No recent errors found" in result["answer"]
        assert result["confidence"] == 0.8

    async def test_errors_without_messages(self, db, assistant):
        _event(db, "nm1", component_id="4", level="ERROR", message=None)
        _event(db, "nm2", component_id="4", level="ERROR", message=None)
        result = await assistant._handle_failure_question(
            "why is agent-4 failing?", None)
        assert "No common errors" in result["answer"]
        assert result["evidence"]["common_errors"] == {}

    async def test_prediction_enabled_noop(self, db):
        pred = DebugAIAssistant(db_session=db, enable_prediction=True)
        _event(db, "p1", component_id="3", level="ERROR", message="x")
        result = await pred._handle_failure_question("why is agent-3 failing?", None)
        assert result["confidence"] == 0.85

    async def test_exception(self, db):
        bad = DebugAIAssistant(db_session=_BadSession())
        with patch.object(bad.logger, "error"):
            result = await bad._handle_failure_question("why is agent-1 failing?", None)
        assert result["confidence"] == 0.0


# ============================================================================
# performance question
# ============================================================================

class TestPerformanceQuestion:
    async def test_no_component_clarification(self, db, assistant):
        result = await assistant._handle_performance_question("why is it slow?", None)
        assert result["clarification_needed"] == "component_id"

    async def test_warning_insight(self, db, assistant):
        insight = SimpleNamespace(
            severity="warning", summary="latency high", description="p95 9s",
            confidence_score=0.9, evidence={"p95": 9000},
            suggestions=["profile hot paths"])
        with patch.object(assistant.performance_gen, "analyze_component_latency",
                          new=AsyncMock(return_value=insight)):
            result = await assistant._handle_performance_question(
                "why is agent-1 slow?", None)
        assert result["answer"] == "latency high"
        assert result["description"] == "p95 9s"
        assert result["confidence"] == 0.9
        assert result["suggestions"] == ["profile hot paths"]

    async def test_non_warning_insight(self, db, assistant):
        insight = SimpleNamespace(
            severity="info", summary="all good", description=None,
            confidence_score=0.8, evidence={}, suggestions=None)
        with patch.object(assistant.performance_gen, "analyze_component_latency",
                          new=AsyncMock(return_value=insight)):
            result = await assistant._handle_performance_question(
                "why is agent-1 slow?", None)
        assert result["answer"] == "all good"
        assert result["suggestions"] == ["Continue monitoring", "No action needed"]

    async def test_no_data(self, db, assistant):
        with patch.object(assistant.performance_gen, "analyze_component_latency",
                          new=AsyncMock(return_value=None)):
            result = await assistant._handle_performance_question(
                "why is agent-1 slow?", None)
        assert "No performance data available" in result["answer"]
        assert result["confidence"] == 0.6

    async def test_exception(self, db, assistant):
        with patch.object(assistant.performance_gen, "analyze_component_latency",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            result = await assistant._handle_performance_question(
                "why is agent-1 slow?", None)
        assert result["confidence"] == 0.0


# ============================================================================
# consistency question
# ============================================================================

class TestConsistencyQuestion:
    async def test_no_match_clarification(self, db, assistant):
        result = await assistant._handle_consistency_question(
            "is the data consistent?", None)
        assert result["clarification_needed"] == "operation_or_component"

    async def test_operation_with_no_activity(self, db, assistant):
        result = await assistant._handle_consistency_question(
            "is op-999 consistent?", None)
        assert "No activity found for operation -999" in result["answer"]
        assert result["confidence"] == 0.7

    async def test_operation_with_components_and_insight(self, db, assistant):
        _event(db, "c1", component_id="node-1", correlation_id="op-100",
               level="INFO", message="sync")
        _event(db, "c2", component_id="node-2", correlation_id="op-100",
               level="INFO", message="sync")
        insight = SimpleNamespace(
            summary="nodes in sync", description="ok", confidence_score=0.95,
            evidence={"checked": 2}, suggestions=["keep going"])
        with patch.object(assistant.consistency_gen, "analyze_data_flow",
                          new=AsyncMock(return_value=insight)):
            result = await assistant._handle_consistency_question(
                "is op-100 consistent?", None)
        assert result["answer"] == "nodes in sync"
        assert result["confidence"] == 0.95
        assert result["related_insights"] == [insight]

    async def test_operation_with_components_no_insight(self, db, assistant):
        _event(db, "c3", component_id="node-1", correlation_id="op-101", level="INFO")
        with patch.object(assistant.consistency_gen, "analyze_data_flow",
                          new=AsyncMock(return_value=None)):
            result = await assistant._handle_consistency_question(
                "is op-101 consistent?", None)
        assert result["answer"] == "No consistency data available"
        assert result["confidence"] == 0.5

    async def test_component_only_match(self, db, assistant):
        """BUG-FIX W70-5 regression: a component-only consistency question
        must produce an answer, not silently return None."""
        _event(db, "c4", component_id="node-1", correlation_id="op-202",
               level="INFO", message="sync")
        result = await assistant._handle_consistency_question(
            "is agent-1 data consistent?", None)
        assert result is not None
        assert "answer" in result

    async def test_exception(self, db, assistant):
        with patch.object(assistant.consistency_gen, "analyze_data_flow",
                          new=AsyncMock(side_effect=RuntimeError("boom"))):
            _event(db, "c5", component_id="node-1", correlation_id="op-203", level="INFO")
            result = await assistant._handle_consistency_question(
                "is op-203 consistent?", None)
        assert result["confidence"] == 0.0


# ============================================================================
# error patterns question
# ============================================================================

class TestErrorPatternsQuestion:
    async def test_no_patterns(self, db, assistant):
        result = await assistant._handle_error_patterns_question("patterns?", None)
        assert "No significant error patterns" in result["answer"]
        assert result["confidence"] == 0.75

    async def test_with_patterns(self, db, assistant):
        _insight(db, "pat-1", evidence={"occurrence_count": 7},
                 suggestions=["investigate"])
        result = await assistant._handle_error_patterns_question("patterns?", None)
        assert "Found 1 error pattern(s)" in result["answer"]
        assert result["confidence"] == 0.80
        assert result["evidence"]["patterns"][0]["occurrences"] == 7
        assert result["evidence"]["patterns"][0]["severity"] == "warning"
        assert result["related_insights"][0].id == "pat-1"

    async def test_pattern_without_evidence(self, db, assistant):
        _insight(db, "pat-2", evidence=None)
        result = await assistant._handle_error_patterns_question("patterns?", None)
        assert result["evidence"]["patterns"][0]["occurrences"] == 0

    async def test_exception(self, db):
        bad = DebugAIAssistant(db_session=_BadSession())
        with patch.object(bad.logger, "error"):
            result = await bad._handle_error_patterns_question("patterns?", None)
        assert result["confidence"] == 0.0


# ============================================================================
# general question
# ============================================================================

class TestGeneralQuestion:
    async def test_operation_progress(self, db, assistant):
        _event(db, "g1", correlation_id="-777", data={"step": 1, "status": "completed"})
        _event(db, "g2", correlation_id="-777", data={"step": 2, "status": "completed"})
        result = await assistant._handle_general_question(
            "what happened with op-777?", None)
        assert "Operation -777 completed with 100% progress" in result["answer"]
        assert result["confidence"] == 0.85
        assert result["evidence"]["total_steps"] == 2

    async def test_system_low_error_rate(self, db, assistant):
        result = await assistant._handle_general_question("give me a summary", None)
        assert "No critical issues" in result["answer"]
        assert result["confidence"] == 0.75

    async def test_system_high_error_rate(self, db, assistant):
        for i in range(5):
            _event(db, f"ge-{i}", component_id="sys-1", level="ERROR")
        for i in range(5):
            _event(db, f"go-{i}", component_id="sys-2", level="INFO")
        result = await assistant._handle_general_question("give me a summary", None)
        assert "Error rate is 50.0%" in result["answer"]
        assert "Investigate high error rate" in result["suggestions"]

    async def test_exception(self, db):
        bad = DebugAIAssistant(db_session=_BadSession())
        with patch.object(bad.logger, "error"):
            result = await bad._handle_general_question("summary please", None)
        assert result["confidence"] == 0.0


# ============================================================================
# suggestion helpers
# ============================================================================

class TestSuggestionHelpers:
    def test_generate_failure_suggestions_with_insights(self, db, assistant):
        errors = [_event(db, "sf-1", level="ERROR", message="boom")]
        insights = [_insight(db, "sf-ins", suggestions=["fix the thing", "fix the thing"])]
        suggestions = assistant._generate_failure_suggestions(errors, insights)
        assert suggestions == ["fix the thing"]

    def test_generate_failure_suggestions_generic(self, db, assistant):
        errors = [_event(db, "sf-2", level="ERROR", message="boom")]
        suggestions = assistant._generate_failure_suggestions(errors, [])
        assert "Review error logs for details" in suggestions
        assert "Check component configuration" in suggestions
        assert "Verify external dependencies" in suggestions

    def test_generate_failure_suggestions_no_errors(self, db, assistant):
        suggestions = assistant._generate_failure_suggestions([], [])
        assert "Review error logs for details" not in suggestions
        assert "Check component configuration" in suggestions

    def test_system_recommendations_all_branches(self, db, assistant):
        recs = assistant._get_system_recommendations(
            {"error_rate": 0.5, "overall_health_score": 50, "active_operations": 200})
        assert recs == [
            "Investigate high error rate",
            "System health requires attention",
            "Consider scaling up",
        ]
        recs = assistant._get_system_recommendations(
            {"error_rate": 0.0, "overall_health_score": 95, "active_operations": 10})
        assert recs == ["System is operating normally"]

    def test_error_response(self, db, assistant):
        response = assistant._error_response("kaboom")
        assert response["confidence"] == 0.0
        assert response["evidence"] == {"error": "kaboom"}
        assert "Check error logs" in response["suggestions"]
