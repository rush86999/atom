"""Coverage wave 32 — core/llm/context/token_counter.py (46% -> 90%+).

Drives every remaining uncovered branch (all unit-level, no network/LLM):
- module import fallback when tiktoken is unavailable (importlib.reload with
  a blocked import, restored afterwards)
- tiktoken encoding failure -> character-based approximation fallback
- empty-text estimate path
- get_model_family detection (claude / command / embed / gemini / fallback)
- _get_encoding cache: anthropic branch + unsupported-family ValueError
- ContextValidator: init, validate_request_fits (fits + exceeds),
  get_model_context_limit (exact / prefix / default), truncate_to_fit
  (fits / max_tokens clamp / truncate-at-boundary), estimate_request_tokens,
  _truncate_at_boundary (empty / newline / sentence / word / fall-through)
"""
import builtins
import importlib
import sys
from unittest import mock

import pytest

from core.llm.context.token_counter import ContextValidator, ModelFamily, TokenCounter


_REAL_IMPORT = builtins.__import__


def _block_tiktoken(name, *args, **kwargs):
    if name == "tiktoken":
        raise ImportError("No module named 'tiktoken'")
    return _REAL_IMPORT(name, *args, **kwargs)


def test_module_import_without_tiktoken_falls_back():
    """ImportError branch of the module-level tiktoken import."""
    import core.llm.context.token_counter as tc_mod

    with mock.patch.dict(sys.modules, {"tiktoken": None}):
        with mock.patch.object(builtins, "__import__", _block_tiktoken):
            reloaded = importlib.reload(tc_mod)
    try:
        assert reloaded.HAS_TIKTOKEN is False
        counter = reloaded.TokenCounter()
        # No tiktoken -> character approximation everywhere
        assert counter.count_tokens("hello world", "gpt-4o") == 2
        assert counter.count_tokens_by_family("hello world", reloaded.ModelFamily.OPENAI) == 2
    finally:
        importlib.reload(tc_mod)  # restore module state with tiktoken present
        # The restore-reload re-created classes/enums — refresh this module's
        # references so later tests compare against the current definitions.
        globals()["TokenCounter"] = tc_mod.TokenCounter
        globals()["ContextValidator"] = tc_mod.ContextValidator
        globals()["ModelFamily"] = tc_mod.ModelFamily


def test_count_tokens_empty_text_returns_zero():
    assert TokenCounter().count_tokens("", "gpt-4o") == 0


def test_estimate_tokens_empty_text_returns_zero():
    assert TokenCounter().estimate_tokens("") == 0


def test_tiktoken_encoding_failure_falls_back_to_approximation(monkeypatch):
    """tiktoken.get_encoding raising -> warning + char approximation."""
    tc = TokenCounter()

    def boom(family):
        raise RuntimeError("encoding unavailable")

    monkeypatch.setattr(tc, "_get_encoding", boom)
    text = "hello world this is a test"
    assert tc.count_tokens(text, "gpt-4o") == len(text) // 4


def test_model_family_detection():
    tc = TokenCounter()
    assert tc.get_model_family("claude-3-5-sonnet") is ModelFamily.ANTHROPIC
    assert tc.get_model_family("Claude-3-Opus") is ModelFamily.ANTHROPIC
    assert tc.get_model_family("command-r") is ModelFamily.COHERE
    assert tc.get_model_family("embed-english-v3.0") is ModelFamily.COHERE
    assert tc.get_model_family("gemini-1.5-pro") is ModelFamily.GOOGLE
    assert tc.get_model_family("some-unknown-model") is ModelFamily.FALLBACK


def test_get_encoding_anthropic_branch_caches():
    TokenCounter._encoding_cache.pop(ModelFamily.ANTHROPIC, None)
    try:
        counter = TokenCounter()
        enc = counter._get_encoding(ModelFamily.ANTHROPIC)
        assert enc is TokenCounter._encoding_cache[ModelFamily.ANTHROPIC]
        assert counter._get_encoding(ModelFamily.ANTHROPIC) is enc
    finally:
        TokenCounter._encoding_cache.pop(ModelFamily.ANTHROPIC, None)


def test_get_encoding_unsupported_family_raises():
    TokenCounter._encoding_cache.pop(ModelFamily.COHERE, None)
    with pytest.raises(ValueError, match="No tiktoken encoding"):
        TokenCounter()._get_encoding(ModelFamily.COHERE)


def test_context_validator_validate_request_fits():
    validator = ContextValidator()
    assert validator.validate_request_fits("hello world", "gpt-4o", max_tokens=100) is True
    # exceeds limit via tiktoken path (small text, huge max_tokens)
    assert validator.validate_request_fits("hello world", "gpt-4o", max_tokens=200000) is False
    # exceeds limit via char-estimate path (unknown model, long text) —
    # NOTE: use a FALLBACK-family model here; this env's tiktoken build is
    # pathologically slow encoding >~100k chars
    assert validator.validate_request_fits("x" * 600_000, "unknown-model", max_tokens=0) is False


def test_get_model_context_limit():
    validator = ContextValidator()
    assert validator.get_model_context_limit("gpt-4o") == 128000
    assert validator.get_model_context_limit("GPT-4") == 8192
    assert validator.get_model_context_limit("claude-3-5-sonnet-20241022") == 200000
    assert validator.get_model_context_limit("text-embedding-3-large") == 8191
    assert validator.get_model_context_limit("unknown-frontier-model") == ContextValidator.DEFAULT_CONTEXT_LIMIT


def test_truncate_to_fit_returns_text_when_fits():
    validator = ContextValidator()
    text = "hello world, this fits easily"
    assert validator.truncate_to_fit(text, "gpt-4o") == text


def test_truncate_to_fit_max_tokens_clamp():
    validator = ContextValidator()
    text = "hello world"
    assert validator.truncate_to_fit(text, "gpt-4o", max_tokens=100) == text


def test_truncate_to_fit_truncates_long_text():
    validator = ContextValidator()
    text = "sentence one. " + "filler words here " * 500
    truncated = validator.truncate_to_fit(text, "gpt-4", reserve_for_output=7500)
    assert len(truncated) < len(text)
    assert text.startswith(truncated)


def test_estimate_request_tokens():
    validator = ContextValidator()
    messages = [
        {"role": "user", "content": "hello world"},
        {"role": "assistant", "content": ""},
        {"role": "system"},
    ]
    total = validator.estimate_request_tokens(messages, "gpt-4o")
    assert total == (2 + 10) + (0 + 10) + (0 + 10)


def test_truncate_at_boundary_empty():
    assert ContextValidator()._truncate_at_boundary("") == ""


def test_truncate_at_boundary_newline():
    text = "a" * 90 + "\nremaining text"
    assert ContextValidator()._truncate_at_boundary(text) == "a" * 90 + "\n"


def test_truncate_at_boundary_sentence_end():
    text = "x" * 90 + ". more text after"
    assert ContextValidator()._truncate_at_boundary(text) == "x" * 90 + ". "


def test_truncate_at_boundary_word_boundary():
    text = "y" * 95 + " final"
    assert ContextValidator()._truncate_at_boundary(text) == "y" * 95


def test_truncate_at_boundary_no_boundary_returns_unchanged():
    text = "m" * 50 + ". " + "n" * 50
    assert ContextValidator()._truncate_at_boundary(text) == text
