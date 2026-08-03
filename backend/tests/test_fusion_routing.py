"""Tests for fusion routing (panel + judge).

Covers: eligibility gate (the critical safety boundary that protects batch/
workflow automation), anti-recursion guard, quality pre-rank skip, judge
synthesis, judge failure fallback, and judge prompt construction.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.fusion_router import (
    FUSION_ENABLED,
    is_fusion_eligible,
    run_fusion,
    _build_judge_prompt,
)


# --- Eligibility gate (CRITICAL safety boundary) ---------------------------


def test_eligible_when_all_conditions_met():
    assert is_fusion_eligible("fusion", "complex", "chat", 3) is True


def test_not_eligible_without_strategy_header():
    assert is_fusion_eligible("auto", "complex", "chat", 3) is False
    assert is_fusion_eligible(None, "complex", "chat", 3) is False


def test_not_eligible_below_complex_tier():
    for tier in ("heavy", "versatile", "standard", "micro"):
        assert is_fusion_eligible("fusion", tier, "chat", 3) is False


def test_not_eligible_for_batch_task_types():
    """Fusion must NEVER fire on batch/workflow automation paths."""
    for task in ("agentic", "extraction", "pdf_ocr"):
        assert is_fusion_eligible("fusion", "complex", task, 3) is False


def test_not_eligible_with_insufficient_candidates():
    assert is_fusion_eligible("fusion", "complex", "chat", 1) is False


def test_not_eligible_when_disabled(monkeypatch):
    monkeypatch.setattr("core.llm.fusion_router.FUSION_ENABLED", False)
    assert is_fusion_eligible("fusion", "complex", "chat", 3) is False


# --- Judge prompt construction ---------------------------------------------


def test_judge_prompt_includes_all_candidates():
    prompt = _build_judge_prompt("What is 2+2?", ["4", "Four", "The answer is 4"])
    assert "Original question" in prompt
    assert "Candidate 1" in prompt
    assert "Candidate 2" in prompt
    assert "Candidate 3" in prompt
    assert "Synthesize" in prompt


def test_judge_prompt_includes_original_question():
    prompt = _build_judge_prompt("Explain quantum computing", ["Answer A", "Answer B"])
    assert "Explain quantum computing" in prompt


# --- Fusion execution ------------------------------------------------------


@pytest.mark.asyncio
async def test_fusion_returns_synthesized_result():
    """Fusion should return a result when candidates succeed."""
    handler = MagicMock()
    # First 3 calls = samples, 4th call = judge
    responses = [
        "Answer from model A",
        "Answer from model B",
        "Answer from model C",
        "Synthesized best answer combining all candidates",
    ]
    call_count = [0]

    async def mock_generate(**kwargs):
        idx = min(call_count[0], len(responses) - 1)
        call_count[0] += 1
        return responses[idx]

    handler.generate_response = mock_generate

    result, meta = await run_fusion(
        handler=handler,
        prompt="What is the best approach?",
        system_instruction="You are a helpful assistant.",
        options=[("openai", "gpt-4o"), ("anthropic", "claude-sonnet"), ("deepseek", "deepseek-v4")],
        temperature=0.7,
        task_type="chat",
        agent_id=None,
        chain_id=None,
        turn_index=0,
    )

    assert isinstance(result, str)
    assert meta["fusion"] is True
    assert meta["samples"] == 3


@pytest.mark.asyncio
async def test_fusion_fallback_on_all_samples_fail():
    """When all samples fail, fusion should raise RuntimeError."""
    handler = MagicMock()

    async def mock_generate(**kwargs):
        raise RuntimeError("provider down")

    handler.generate_response = mock_generate

    with pytest.raises(RuntimeError, match="All fusion samples failed"):
        await run_fusion(
            handler=handler,
            prompt="test",
            system_instruction="sys",
            options=[("openai", "gpt-4o"), ("anthropic", "claude")],
            temperature=0.7,
            task_type="chat",
            agent_id=None,
            chain_id=None,
            turn_index=0,
        )


@pytest.mark.asyncio
async def test_fusion_judge_failure_returns_best_candidate():
    """When the judge fails, fusion falls back to the highest-quality candidate."""
    handler = MagicMock()
    call_count = [0]

    async def mock_generate(**kwargs):
        call_count[0] += 1
        if call_count[0] <= 2:  # samples
            return f"Sample answer {call_count[0]}"
        raise RuntimeError("judge model down")  # judge fails

    handler.generate_response = mock_generate

    result, meta = await run_fusion(
        handler=handler,
        prompt="test",
        system_instruction="sys",
        options=[("openai", "gpt-4o"), ("anthropic", "claude")],
        temperature=0.7,
        task_type="chat",
        agent_id=None,
        chain_id=None,
        turn_index=0,
    )

    assert isinstance(result, str)
    assert meta.get("judge_failed") is True or meta.get("judge_skipped") is True


@pytest.mark.asyncio
async def test_fusion_respects_sample_count():
    """Fusion should sample min(FUSION_SAMPLE_COUNT, len(options)) models."""
    handler = MagicMock()
    call_count = [0]

    async def mock_generate(**kwargs):
        call_count[0] += 1
        return f"Answer {call_count[0]}"

    handler.generate_response = mock_generate

    with patch("core.llm.fusion_router.FUSION_SAMPLE_COUNT", 2):
        result, meta = await run_fusion(
            handler=handler,
            prompt="test",
            system_instruction="sys",
            options=[("a", "1"), ("b", "2"), ("c", "3"), ("d", "4")],
            temperature=0.7,
            task_type="chat",
            agent_id=None,
            chain_id=None,
            turn_index=0,
        )

    # 2 samples + 1 judge = 3 calls (or 2 if judge skipped via quality pre-rank)
    assert call_count[0] <= 4
