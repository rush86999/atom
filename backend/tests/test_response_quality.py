"""
Tests for response quality assessment and the build_feedback mapping.

These verify that the previously-placeholder quality fields on RoutingFeedback
are now populated from real outcome signals (truncation, empty, refusal,
schema error, exception) — the foundation of outcome-based learning.
"""

from __future__ import annotations

import pytest

from core.llm.response_quality import (
    ResponseQuality,
    assess_response_quality,
)


class TestAssessResponseQuality:
    """The quality-assessment heuristics."""

    def test_normal_substantive_content_passes(self):
        q = assess_response_quality(
            content="Here is a detailed answer to your question. " * 20,
            finish_reason="stop",
        )
        assert q.success is True
        assert q.quality_satisfied is True
        assert 0.7 <= q.quality_score <= 0.95
        assert q.issues == []

    def test_truncation_flagged(self):
        q = assess_response_quality(
            content="partial response...",
            finish_reason="length",
        )
        assert q.success is True
        assert q.quality_satisfied is False
        assert "truncated" in q.issues
        assert q.quality_score < 0.5

    def test_empty_content_flagged(self):
        q = assess_response_quality(content="   ", finish_reason="stop")
        assert q.success is True
        assert q.quality_satisfied is False
        assert "empty" in q.issues

    def test_refusal_flagged(self):
        q = assess_response_quality(
            content="I'm sorry, but I can't help with that request.",
            finish_reason="stop",
        )
        assert q.success is True
        assert q.quality_satisfied is False
        assert "refusal" in q.issues

    def test_schema_error_flagged_but_api_succeeded(self):
        q = assess_response_quality(
            content='{"broken": json',
            schema_error=True,
        )
        assert q.success is True  # API worked
        assert q.quality_satisfied is False
        assert "schema_error" in q.issues
        assert q.quality_score == pytest.approx(0.2)

    def test_exception_is_failure(self):
        q = assess_response_quality(
            content=None,
            exception=ConnectionError("timed out"),
        )
        assert q.success is False
        assert q.quality_satisfied is False
        assert q.quality_score == 0.0
        assert len(q.issues) == 1

    def test_exception_classified(self):
        q = assess_response_quality(content=None, exception=TimeoutError("timeout"))
        assert "timeout" in q.issues

        q2 = assess_response_quality(
            content=None,
            exception=Exception("rate limit exceeded"),
        )
        assert "rate_limited" in q2.issues

    def test_graded_score_grows_with_substance(self):
        short = assess_response_quality(content="ok done.", finish_reason="stop")
        medium = assess_response_quality(content="x" * 300, finish_reason="stop")
        long = assess_response_quality(content="x" * 1000, finish_reason="stop")
        assert medium.quality_score > short.quality_score
        assert long.quality_score >= medium.quality_score


class TestBuildFeedback:
    """The mapping from quality assessment to RoutingFeedback."""

    def test_build_feedback_maps_fields(self):
        from core.learning_llm_router import LearningBasedRouter, RoutingFeedback

        quality = ResponseQuality(
            success=True, quality_satisfied=False,
            quality_score=0.3, issues=["truncated"],
        )
        fb = LearningBasedRouter.build_feedback(
            routing_result_id="rid-1",
            tenant_id="t1",
            model_id="gpt-4o",
            task_type="code_generation",
            quality=quality,
            actual_cost=0.0023,
            actual_latency_ms=540.0,
        )
        assert isinstance(fb, RoutingFeedback)
        assert fb.routing_result_id == "rid-1"
        assert fb.model_id == "gpt-4o"
        assert fb.success is True
        assert fb.quality_satisfied is False
        assert fb.user_satisfaction == 0.3  # graded, not binary
        assert fb.actual_cost == 0.0023
        assert fb.actual_latency_ms == 540.0
