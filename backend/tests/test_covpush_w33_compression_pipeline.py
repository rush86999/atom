"""Coverage wave 33 — compression pipeline token counting (TDD, real bug).

`CompressionPipeline.compress_tool_output` called ``TokenCounter.count_tokens``
with a single positional argument, but the counter requires ``(text, model)`` —
every call raised TypeError, was swallowed by the best-effort ``except``, and
``original_tokens``/``compressed_tokens`` always fell back to ``len(text)//4``.
The pipeline's metrics silently never used the real token counter.
"""
import os

import pytest

from core.llm.compression import COMPRESSION_ENABLED, RTK_ENABLED, CompressionPipeline


class _StrictCounter:
    """TokenCounter stand-in that fails loudly when called without a model."""

    def __init__(self):
        self.calls = []

    def count_tokens(self, text, model):
        self.calls.append((text, model))
        return 40


@pytest.fixture
def pipeline(monkeypatch):
    # compress_tool_output imports TokenCounter lazily inside the function.
    monkeypatch.setattr(
        "core.llm.context.token_counter.TokenCounter", _StrictCounter, raising=False
    )
    return CompressionPipeline()


def test_compress_tool_output_counts_tokens_with_model(pipeline, monkeypatch):
    """original_tokens must come from the token counter (with a model), not
    from the len(text)//4 fallback."""
    monkeypatch.setattr("core.llm.compression.RTK_ENABLED", True)
    monkeypatch.setattr("core.llm.compression.COMPRESSION_ENABLED", True)
    # Avoid real RTK compression so the text round-trips unchanged.
    monkeypatch.setattr(pipeline._rtk, "compress", lambda text: text)
    result, metrics = pipeline.compress_tool_output("hello world " * 20)
    assert metrics.original_tokens == 40
    assert metrics.compressed_tokens == 40
    assert result == "hello world " * 20


def test_compress_tool_output_disabled_counts_original_only(pipeline, monkeypatch):
    """When compression flags are off, only the original count is computed."""
    monkeypatch.setattr("core.llm.compression.RTK_ENABLED", False)
    monkeypatch.setattr("core.llm.compression.COMPRESSION_ENABLED", False)
    _, metrics = pipeline.compress_tool_output("some text here")
    assert metrics.original_tokens == 40
    assert metrics.compressed_tokens == 40


def test_compress_tool_output_empty_input(pipeline):
    result, metrics = pipeline.compress_tool_output("")
    assert result == ""
    assert metrics.original_tokens == 0
    assert metrics.compressed_tokens == 0
