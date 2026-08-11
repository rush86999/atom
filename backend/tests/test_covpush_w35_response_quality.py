"""Coverage wave 35 — core/llm/response_quality.py (92% → 100%).

Covers the remaining branches: very-long-run score diminution (len > 8000)
and the _classify_exception mapping for context_length, auth_error, and the
provider_error fallback.
"""
import pytest

from core.llm.response_quality import _classify_exception, assess_response_quality


class TestVeryLongResponses:
    def test_over_8000_chars_diminished_score(self):
        result = assess_response_quality(content="x" * 8500)
        assert result.success is True
        assert result.quality_score == 0.78

    def test_score_capped_at_095(self):
        # 0.85 base for >= 800 chars; the cap should keep it at 0.85 — assert
        # the min() clamp does not exceed 0.95 for any length
        result = assess_response_quality(content="y" * 5000)
        assert result.quality_score <= 0.95


class TestClassifyException:
    def test_context_length(self):
        class FakeError(Exception):
            pass
        assert _classify_exception(FakeError("This model's maximum context length is 4096 tokens")) == "context_length"

    def test_auth_error_by_message(self):
        class FakeError(Exception):
            pass
        assert _classify_exception(FakeError("Invalid API key provided")) == "auth_error"

    def test_auth_error_by_name(self):
        assert _classify_exception(ValueError("401 Unauthorized")) == "auth_error"

    def test_provider_error_fallback(self):
        class FakeError(Exception):
            pass
        assert _classify_exception(FakeError("mystery failure")) == "provider_error"
