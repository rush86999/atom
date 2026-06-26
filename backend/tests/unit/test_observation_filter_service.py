"""
Unit tests for core.observation_filter_service.ObservationFilterService
(single-tenant upstream port).

Same surface as the SaaS tests, minus the tenant_id threading case.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from core import observation_filter_service as obs_module
from core.observation_filter_service import ObservationFilterService


def _embedding_from_text(text: str, dim: int = 16) -> list[float]:
    vec = np.zeros(dim, dtype=float)
    for i, ch in enumerate(text):
        vec[i % dim] += ord(ch) % 97
    norm = np.linalg.norm(vec)
    if norm == 0:
        vec[0] = 1.0
        norm = 1.0
    return (vec / norm).tolist()


@pytest.fixture
def fake_llm():
    llm = Mock()
    llm.generate_embedding = AsyncMock()
    return llm


@pytest.fixture
def service(fake_llm, monkeypatch):
    monkeypatch.setattr(obs_module, "OBSERVATION_FILTER_ENABLED", True)
    return ObservationFilterService(llm=fake_llm)


def _obs(text: str) -> str:
    return f"Observation: {text}\n"


@pytest.mark.asyncio
async def test_rule_filter_removes_exact_duplicates(service):
    history = _obs("Saved record 42") + _obs("Saved record 42") + _obs("Done")
    filtered, metrics = await service.filter_history(history, current_step=5, task_input="t")
    assert filtered.count("Saved record 42") == 1
    assert metrics["savings_tokens"] >= 0


@pytest.mark.asyncio
async def test_semantic_collapse_keeps_last_n(service, fake_llm):
    near_dup = "User logged in from 1.2.3.4"
    history = ""
    for _ in range(6):
        history += _obs(near_dup)

    async def fake_embed(text, **kwargs):
        return _embedding_from_text(near_dup)

    fake_llm.generate_embedding = fake_embed

    filtered, _ = await service.filter_history(history, current_step=8, task_input="t")
    count = filtered.count(near_dup)
    assert count <= service.KEEP_LAST_N, f"expected <= KEEP_LAST_N, got {count}"


@pytest.mark.asyncio
async def test_returns_metrics_dict(service):
    history = _obs("a") + _obs("b")
    _, metrics = await service.filter_history(history, current_step=2, task_input="t")
    assert isinstance(metrics, dict)
    for key in ("savings_tokens", "original_tokens", "filtered_tokens", "embedding_pass"):
        assert key in metrics, f"missing metric {key}"


@pytest.mark.asyncio
async def test_short_history_skips_embedding_pass(service, fake_llm):
    history = _obs("a") + _obs("b")
    _, metrics = await service.filter_history(history, current_step=1, task_input="t")
    assert metrics["embedding_pass"] is False
    fake_llm.generate_embedding.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_exception_returns_history_unchanged(service, fake_llm):
    async def boom(text, **kwargs):
        raise RuntimeError("embedding provider down")

    fake_llm.generate_embedding = boom

    history = _obs("alpha") + _obs("beta") + _obs("gamma")
    filtered, metrics = await service.filter_history(history, current_step=7, task_input="t")
    assert "alpha" in filtered
    assert "beta" in filtered
    assert "gamma" in filtered
    assert metrics.get("embedding_pass") in (False, True)
    assert metrics["savings_tokens"] >= 0


@pytest.mark.asyncio
async def test_flag_disabled_is_noop(fake_llm, monkeypatch):
    monkeypatch.setattr(obs_module, "OBSERVATION_FILTER_ENABLED", False)
    service = ObservationFilterService(llm=fake_llm)
    history = _obs("a") + _obs("b")
    filtered, metrics = await service.filter_history(history, current_step=5, task_input="t")
    assert filtered == history
    assert metrics.get("enabled") is False
    fake_llm.generate_embedding.assert_not_called()  # type: ignore[attr-defined]
