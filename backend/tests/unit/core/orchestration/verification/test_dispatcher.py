"""Tests for the VerificationOrchestrator dispatcher.

Covers:
  * Domain → strategy routing (each domain reaches its mapped verifier).
  * Universal VOTING fallback when a strategy returns winner=None.
  * LLM-absent degradation (GROUNDED/JUDGE → voting).
  * Strategy that raises → orchestrator never propagates, falls back.
  * Field Guide feedback written only for *inferred* domains.
  * Explicit task_domain suppresses feedback recording.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

BACKEND_DIR = Path(__file__).parents[5]  # tests/unit/core/orchestration/verification/ → backend/
sys.path.insert(0, str(BACKEND_DIR))

from core.orchestration.verification.base import (
    VerificationResult,
    VerificationStrategy,
    Verifier,
)
from core.orchestration.verification.domain import TaskDomain
from core.orchestration.verification.dispatcher import VerificationOrchestrator


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------
class _Step:
    def __init__(self, **kw):
        self.step_id = kw.pop("step_id", "s1")
        self.name = kw.pop("name", "")
        self.description = kw.pop("description", "")
        self.capability = kw.pop("capability", "")
        self.parameters = kw.pop("parameters", {})


class _Ctx:
    """Plain context object — supports attribute stamping."""
    def __init__(self, workspace_id="ws_test", **kw):
        self.workspace_id = workspace_id
        self.shared_context = kw.pop("shared_context", {})


class _RecordingVerifier(Verifier):
    """Verifier stub that records calls and returns a canned result."""
    def __init__(self, strategy, result):
        self.strategy = strategy
        self._result = result
        self.calls: List[Dict[str, Any]] = []

    async def verify(self, candidates, step, context):
        self.calls.append({"candidates": candidates, "step": step})
        return self._result


class _RaisingVerifier(Verifier):
    strategy = VerificationStrategy.FORMAL
    async def verify(self, candidates, step, context):
        raise RuntimeError("boom")


class _FakeFieldGuide:
    def __init__(self):
        self.updates: List[Dict[str, Any]] = []

    def update_field_guide(self, workspace_id, topic, insight_text, *, agent_id=None):
        self.updates.append({
            "workspace_id": workspace_id,
            "topic": topic,
            "insight_text": insight_text,
            "agent_id": agent_id,
        })


def _run(coro):
    return asyncio.run(coro)


def _make_orchestrator(strategy_results, *, field_guide_service=None, verifiers=None):
    """Build an orchestrator where each strategy returns a canned result.

    ``strategy_results`` maps VerificationStrategy → VerificationResult.
    """
    if verifiers is None:
        verifiers = {
            strat: _RecordingVerifier(strat, result)
            for strat, result in strategy_results.items()
        }
    return VerificationOrchestrator(
        field_guide_service=field_guide_service,
        verifiers=verifiers,
    )


# ===========================================================================
# Routing
# ===========================================================================
class TestRouting:
    def test_unknown_domain_uses_voting(self):
        results = {VerificationStrategy.VOTING: VerificationResult(
            winner={"x": 1}, strategy=VerificationStrategy.VOTING,
            domain=TaskDomain.UNKNOWN, confidence=1.0,
        )}
        orch = _make_orchestrator(results)
        step = _Step()  # no keywords → UNKNOWN
        result = _run(orch.verify([{"x": 1}], step, _Ctx()))
        assert result.winner == {"x": 1}
        assert result.strategy == VerificationStrategy.VOTING
        assert result.fallback_used is False

    def test_code_domain_uses_code_pipeline(self):
        results = {
            VerificationStrategy.CODE_PIPELINE: VerificationResult(
                winner={"code": "print(1)"}, strategy=VerificationStrategy.CODE_PIPELINE,
                domain=TaskDomain.CODE, confidence=1.0,
            ),
        }
        # Voting must still be registered (fallback path).
        results[VerificationStrategy.VOTING] = VerificationResult(
            winner=None, strategy=VerificationStrategy.VOTING, domain=TaskDomain.CODE,
        )
        orch = _make_orchestrator(results)
        step = _Step(name="implement the python function")
        result = _run(orch.verify([{"code": "print(1)"}], step, _Ctx()))
        assert result.winner == {"code": "print(1)"}
        assert result.strategy == VerificationStrategy.CODE_PIPELINE
        assert result.fallback_used is False

    def test_explicit_task_domain_tag_overrides_inference(self):
        # name would infer CODE, but explicit tag says MATH → FORMAL.
        results = {
            VerificationStrategy.FORMAL: VerificationResult(
                winner={"answer": "42"}, strategy=VerificationStrategy.FORMAL,
                domain=TaskDomain.MATH, confidence=1.0,
            ),
            VerificationStrategy.EXECUTION: VerificationResult(
                winner=None, strategy=VerificationStrategy.EXECUTION, domain=TaskDomain.MATH,
            ),
            VerificationStrategy.VOTING: VerificationResult(
                winner=None, strategy=VerificationStrategy.VOTING, domain=TaskDomain.MATH,
            ),
        }
        orch = _make_orchestrator(results)
        step = _Step(name="implement python", parameters={"task_domain": "math"})
        result = _run(orch.verify([{"answer": "42"}], step, _Ctx()))
        assert result.strategy == VerificationStrategy.FORMAL
        assert result.winner == {"answer": "42"}

    def test_explicit_strategy_override_takes_precedence(self):
        results = {
            VerificationStrategy.JUDGE: VerificationResult(
                winner="prose-winner", strategy=VerificationStrategy.JUDGE,
                domain=TaskDomain.CODE, confidence=1.0,
            ),
        }
        for strat in VerificationStrategy:
            results.setdefault(strat, VerificationResult(
                winner=None, strategy=strat, domain=TaskDomain.CODE,
            ))
        orch = _make_orchestrator(results)
        # CODE domain would normally route to CODE_PIPELINE, but the caller
        # forced JUDGE.
        step = _Step(name="implement python", parameters={"verification_strategy": "judge"})
        result = _run(orch.verify(["a", "b"], step, _Ctx()))
        assert result.strategy == VerificationStrategy.JUDGE


# ===========================================================================
# Universal fallback
# ===========================================================================
class TestFallback:
    def test_winner_none_falls_back_to_voting(self):
        # Use an explicit strategy override to test the EXECUTION→voting
        # fallback path in isolation (CODE now maps to CODE_PIPELINE by
        # default, so we force EXECUTION via the step override).
        results = {
            VerificationStrategy.EXECUTION: VerificationResult(
                winner=None, strategy=VerificationStrategy.EXECUTION,
                domain=TaskDomain.UNKNOWN, reason="no candidate passed",
            ),
            VerificationStrategy.VOTING: VerificationResult(
                winner={"voted": True}, strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.UNKNOWN, confidence=0.66,
            ),
        }
        orch = _make_orchestrator(results)
        step = _Step(parameters={"verification_strategy": "execution"})
        result = _run(orch.verify([{"code": "bad"}], step, _Ctx()))
        # Winner came from voting…
        assert result.winner == {"voted": True}
        # …but strategy is preserved as EXECUTION with fallback_used=True.
        assert result.strategy == VerificationStrategy.EXECUTION
        assert result.fallback_used is True
        assert "execution → voting fallback" in (result.reason or "")

    def test_strategy_raising_falls_back_to_voting(self):
        verifiers = {
            VerificationStrategy.FORMAL: _RaisingVerifier(),
            VerificationStrategy.VOTING: _RecordingVerifier(
                VerificationStrategy.VOTING,
                VerificationResult(winner={"v": 1}, strategy=VerificationStrategy.VOTING, domain=TaskDomain.MATH),
            ),
        }
        for strat in VerificationStrategy:
            verifiers.setdefault(strat, _RecordingVerifier(
                strat, VerificationResult(winner=None, strategy=strat, domain=TaskDomain.MATH),
            ))
        orch = VerificationOrchestrator(verifiers=verifiers)
        step = _Step(name="solve the calculus equation")
        result = _run(orch.verify([{"answer": "x"}], step, _Ctx()))
        assert result.winner == {"v": 1}
        assert result.fallback_used is True

    def test_voting_returning_none_stays_none(self):
        # If even voting can't decide (e.g. empty candidates), winner stays None.
        results = {
            VerificationStrategy.VOTING: VerificationResult(
                winner=None, strategy=VerificationStrategy.VOTING,
                domain=TaskDomain.UNKNOWN, reason="no candidates",
            ),
        }
        orch = _make_orchestrator(results)
        result = _run(orch.verify([], _Step(), _Ctx()))
        assert result.winner is None
        assert result.fallback_used is False  # voting was the chosen strategy

    def test_empty_candidates_unknown_domain(self):
        results = {strat: VerificationResult(
            winner=None, strategy=strat, domain=TaskDomain.UNKNOWN,
        ) for strat in VerificationStrategy}
        orch = _make_orchestrator(results)
        result = _run(orch.verify([], _Step(), _Ctx()))
        assert result.winner is None


# ===========================================================================
# Graceful degradation (no LLM wired)
# ===========================================================================
class TestDegradation:
    def test_grounded_without_llm_falls_back_to_voting(self):
        # Default orchestrator has no llm_service → GROUNDED returns None.
        orch = VerificationOrchestrator()  # no services wired
        step = _Step(
            name="answer the question",
            parameters={"sources": ["Paris is the capital of France."]},
        )
        candidates = [{"answer": "Paris"}, {"answer": "London"}]
        result = _run(orch.verify(candidates, step, _Ctx()))
        # Two distinct candidates → voting can't form a majority → None
        # (but no crash, no infinite loop).
        assert result.winner is None or isinstance(result.winner, dict)
        assert result.fallback_used is True

    def test_judge_without_llm_falls_back_to_voting(self):
        orch = VerificationOrchestrator()
        step = _Step(name="write a summary email")
        result = _run(orch.verify(["draft A", "draft B"], step, _Ctx()))
        # Voting over two distinct strings → no majority → None.
        assert result.winner is None or isinstance(result.winner, str)
        assert result.fallback_used is True

    def test_execution_without_sandbox_falls_back_to_voting(self):
        # No sandbox runtime wired; default get_runtime() will likely
        # return NullRuntime → execution returns failure → voting fallback.
        orch = VerificationOrchestrator()
        step = _Step(name="implement the python function", parameters={"tests": None})
        # All three candidates identical → voting majority picks it.
        candidates = [{"code": "print('hi')"}] * 3
        result = _run(orch.verify(candidates, step, _Ctx()))
        assert result.winner is not None
        assert result.fallback_used is True


# ===========================================================================
# Field Guide feedback
# ===========================================================================
class TestFieldGuideFeedback:
    def test_inferred_domain_writes_feedback(self):
        fg = _FakeFieldGuide()
        # "implement the python function" infers CODE → CODE_PIPELINE.
        results = {VerificationStrategy.CODE_PIPELINE: VerificationResult(
            winner={"x": 1}, strategy=VerificationStrategy.CODE_PIPELINE,
            domain=TaskDomain.CODE, confidence=1.0,
        )}
        results[VerificationStrategy.VOTING] = VerificationResult(
            winner=None, strategy=VerificationStrategy.VOTING, domain=TaskDomain.CODE,
        )
        orch = _make_orchestrator(results, field_guide_service=fg)
        step = _Step(name="implement the python function")  # inferred CODE
        _run(orch.verify([{"x": 1}, {"x": 1}], step, _Ctx(workspace_id="ws1")))
        assert len(fg.updates) == 1
        assert fg.updates[0]["workspace_id"] == "ws1"
        assert fg.updates[0]["topic"] == "Verification Feedback"
        assert "domain=code" in fg.updates[0]["insight_text"]
        assert "strategy=code_pipeline" in fg.updates[0]["insight_text"]
        assert fg.updates[0]["agent_id"] == "verification-orchestrator"

    def test_explicit_domain_suppresses_feedback(self):
        fg = _FakeFieldGuide()
        results = {VerificationStrategy.FORMAL: VerificationResult(
            winner={"answer": "42"}, strategy=VerificationStrategy.FORMAL,
            domain=TaskDomain.MATH, confidence=1.0,
        )}
        results[VerificationStrategy.VOTING] = VerificationResult(
            winner=None, strategy=VerificationStrategy.VOTING, domain=TaskDomain.MATH,
        )
        orch = _make_orchestrator(results, field_guide_service=fg)
        step = _Step(name="solve equation", parameters={"task_domain": "math"})
        _run(orch.verify([{"answer": "42"}], step, _Ctx(workspace_id="ws1")))
        assert fg.updates == []  # explicit tag → no learning-recorded feedback

    def test_no_field_guide_service_is_silent(self):
        # No crash when field_guide_service is None.
        results = {VerificationStrategy.VOTING: VerificationResult(
            winner={"x": 1}, strategy=VerificationStrategy.VOTING,
            domain=TaskDomain.UNKNOWN, confidence=1.0,
        )}
        orch = _make_orchestrator(results, field_guide_service=None)
        result = _run(orch.verify([{"x": 1}, {"x": 1}], _Step(), _Ctx()))
        assert result.winner == {"x": 1}

    def test_feedback_failure_is_swallowed(self):
        class _BrokenFG:
            def update_field_guide(self, *a, **kw):
                raise RuntimeError("db down")
        results = {VerificationStrategy.VOTING: VerificationResult(
            winner={"x": 1}, strategy=VerificationStrategy.VOTING,
            domain=TaskDomain.CODE, confidence=1.0,
        )}
        orch = _make_orchestrator(results, field_guide_service=_BrokenFG())
        step = _Step(name="implement the python function")
        # Must not raise.
        result = _run(orch.verify([{"x": 1}, {"x": 1}], step, _Ctx()))
        assert result.winner == {"x": 1}
