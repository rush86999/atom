"""Coverage wave 17 — OpencodeModelLimits registry + TokenCounter (TDD)."""
import os
from unittest.mock import MagicMock, patch

import pytest

from core.llm.opencode_model_limits import (
    OpencodeModelLimits,
    get_opencode_model_limits,
    weight_from_prices,
)


class TestWeightFromPrices:
    def test_derives_weight(self):
        # baseline price per 1M is a constant; 4x baseline -> weight ~4
        w = weight_from_prices(0.000004, 0.000016)
        assert w >= 1.0

    def test_unknown_pricing_default(self):
        assert weight_from_prices(None, None) == 1.0
        assert weight_from_prices(0, 0) == 1.0

    def test_invalid_pricing_default(self):
        assert weight_from_prices("abc", None) == 1.0


class TestModelLimitsRegistry:
    def _registry(self):
        with patch("core.llm.opencode_model_limits.OPCODE_DEFAULT_MODEL_WEIGHTS", {}):
            return OpencodeModelLimits()

    def test_default_weight(self):
        r = self._registry()
        assert r.get_weight("opencode-go", "unknown-model") == 1.0
        assert r.get_weight("opencode-go", None) == 1.0

    def test_set_and_get_limits(self):
        r = self._registry()
        r.set_model_limits("opencode-go", "kimi-k3", weight=15.0, rpm=20, tpm=500000)
        assert r.get_weight("opencode-go", "kimi-k3") == 15.0
        limits = r.get_model_rate_limits("opencode-go", "kimi-k3")
        assert limits["rpm"] == 20
        assert limits["tpm"] == 500000

    def test_zero_weight_normalized(self):
        r = self._registry()
        r.set_model_limits("p", "m", weight=0.0)
        assert r.get_weight("p", "m") == 1.0

    def test_empty_limits_noop(self):
        r = self._registry()
        r.set_model_limits("p", "m", rpm=5)
        r.set_model_limits("p", "m")  # no values -> existing entry kept
        assert r.get_model_rate_limits("p", "m") == {"rpm": 5}

    def test_empty_model_id_noop(self):
        r = self._registry()
        r.set_model_limits("p", "", weight=3.0)  # no raise
        assert r.get_weight("p", "") == 1.0

    def test_apply_pricing_weight(self):
        r = self._registry()
        w = r.apply_pricing_weight("p", "m", 0.000008, 0.000032)
        assert w >= 1.0
        assert r.get_weight("p", "m") == w

    def test_explicit_weight_wins(self):
        r = self._registry()
        r.set_model_limits("p", "m", weight=5.0)
        w = r.apply_pricing_weight("p", "m", 0.0001, 0.0001)
        assert w == 5.0

    def test_summary(self):
        r = self._registry()
        r.set_model_limits("opencode-go", "kimi-k3", weight=15.0, tpm=1000)
        s = r.summary()
        assert s["provider"] == "opencode-go"
        assert s["weights"]["kimi-k3"] == 15.0
        assert s["model_limits"]["kimi-k3"]["tpm"] == 1000

    def test_env_overrides_valid(self):
        env = '{"m1": {"weight": 3.0, "rpm": 10}}'
        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": env}), \
             patch("core.llm.opencode_model_limits.OPCODE_DEFAULT_MODEL_WEIGHTS", {}):
            r = OpencodeModelLimits()
        assert r.get_weight("opencode-go", "m1") == 3.0
        assert r.get_model_rate_limits("opencode-go", "m1") == {"rpm": 10}

    def test_env_overrides_invalid_json(self):
        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": "not-json"}), \
             patch("core.llm.opencode_model_limits.OPCODE_DEFAULT_MODEL_WEIGHTS", {}):
            r = OpencodeModelLimits()  # no raise
        assert r.get_weight("opencode-go", "m1") == 1.0

    def test_env_overrides_invalid_values(self):
        env = '{"m1": {"weight": "abc"}}'
        with patch.dict(os.environ, {"OPENCODE_MODEL_LIMITS": env}), \
             patch("core.llm.opencode_model_limits.OPCODE_DEFAULT_MODEL_WEIGHTS", {}):
            r = OpencodeModelLimits()  # invalid values skipped, no raise
        assert r.get_weight("opencode-go", "m1") == 1.0

    def test_singleton(self):
        assert get_opencode_model_limits() is get_opencode_model_limits()


class TestTokenCounter:
    def test_count_tokens(self):
        from core.llm.context.token_counter import TokenCounter

        tc = TokenCounter()
        n = tc.count_tokens("hello world this is a test", "gpt-4o")
        assert n >= 1
        assert tc.count_tokens("", "gpt-4o") == 0

    def test_count_tokens_by_family(self):
        from core.llm.context.token_counter import TokenCounter
        from core.llm.context.token_counter import ModelFamily

        tc = TokenCounter()
        n = tc.count_tokens_by_family("hello world", ModelFamily.OPENAI)
        assert n >= 1
        n2 = tc.count_tokens_by_family("hello world", ModelFamily.FALLBACK)
        assert n2 >= 1
