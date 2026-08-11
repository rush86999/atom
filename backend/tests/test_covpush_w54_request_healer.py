"""Coverage wave 54 — core/llm/routing/request_healer.py (78% → 90%+).

- classify: unknown fallback (non-exc) + 401/403 substring branch
- HealingRule abstract methods raise NotImplementedError
- _ParamRenameRule apply with no max_tokens -> unchanged
- _StripMultimodalRule: non-dict message + non-list content skips
- make_default_llm_healer: full success (fenced JSON), patch null, no-change,
  exception tolerance
- _summarize_messages: non-list, non-dict entries, multimodal parts,
  truncation, list content
"""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.llm.routing.request_healer import (
    HealingRule,
    RequestHealer,
    _ParamRenameRule,
    _StripMultimodalRule,
    _summarize_messages,
    make_default_llm_healer,
    classify_error,
)


class TestClassify:
    def test_unknown_fallback(self):
        assert classify_error(RuntimeError("weird")) == "unknown"

    def test_auth_substring(self):
        assert classify_error(
            RuntimeError("authentication failed for provider")) == "non_repairable_4xx"


class TestAbstractRule:
    def test_matches_raises(self):
        rule = HealingRule()
        with pytest.raises(NotImplementedError):
            rule.matches(RuntimeError("x"), {}, "p", "m")

    def test_apply_raises(self):
        rule = HealingRule()
        with pytest.raises(NotImplementedError):
            rule.apply({"a": 1})


class TestParamRenameNoToken:
    def test_apply_without_max_tokens(self):
        rule = _ParamRenameRule()
        patched, keys = rule.apply({"temperature": 0.5})
        assert keys == []
        assert patched == {"temperature": 0.5}


class TestStripMultimodalSkips:
    def test_non_dict_message_skipped(self):
        rule = _StripMultimodalRule()
        patched, keys = rule.apply({"messages": ["just-a-string"]})
        assert patched["messages"] == ["just-a-string"]
        assert keys == []

    def test_non_list_content_skipped(self):
        rule = _StripMultimodalRule()
        patched, keys = rule.apply({"messages": [{"role": "user", "content": "text"}]})
        assert patched["messages"][0]["content"] == "text"
        assert keys == []


class TestLlmHealer:
    def _handler(self, reply):
        h = Mock()
        h.generate_response = AsyncMock(return_value=reply)
        return h

    async def test_success_with_fenced_json(self):
        healer = make_default_llm_healer(self._handler(
            '```json\n{"patch": {"temperature": 0.1, "seed": 7}}\n```'))
        patched, keys = await healer(RuntimeError("boom"), {"temperature": 0.9}, "p", "m")
        assert patched["temperature"] == 0.1
        assert keys == ["temperature", "seed"]

    async def test_patch_null_returns_none(self):
        healer = make_default_llm_healer(self._handler('{"patch": null}'))
        assert await healer(RuntimeError("x"), {}, "p", "m") is None

    async def test_no_changed_keys_returns_none(self):
        healer = make_default_llm_healer(self._handler(
            '{"patch": {"temperature": 0.9}}'))
        assert await healer(RuntimeError("x"), {"temperature": 0.9}, "p", "m") is None

    async def test_disallowed_key_ignored(self):
        healer = make_default_llm_healer(self._handler(
            '{"patch": {"api_key": "leak", "temperature": 0.2}}'))
        patched, keys = await healer(RuntimeError("x"), {"temperature": 0.9}, "p", "m")
        assert "api_key" not in patched
        assert keys == ["temperature"]

    async def test_bad_json_returns_none(self):
        healer = make_default_llm_healer(self._handler("not json at all"))
        assert await healer(RuntimeError("x"), {}, "p", "m") is None

    async def test_exception_returns_none(self):
        h = Mock()
        h.generate_response = AsyncMock(side_effect=RuntimeError("llm down"))
        healer = make_default_llm_healer(h)
        assert await healer(RuntimeError("x"), {}, "p", "m") is None

    async def test_timeout_returns_none(self):
        async def slow(*a, **k):
            import asyncio
            await asyncio.sleep(10)
        h = Mock()
        h.generate_response = slow
        healer = make_default_llm_healer(h)
        with patch("asyncio.wait_for", side_effect=TimeoutError("slow")):
            assert await healer(RuntimeError("x"), {}, "p", "m") is None


class TestSummarizeMessages:
    def test_non_list(self):
        out = _summarize_messages("not a list")
        assert out == [{"role": "unknown", "content": "not a list"}]

    def test_multimodal_parts(self):
        messages = [{"role": "user", "content": [
            {"type": "text", "text": "hi"},
            {"type": "image", "image_url": "..."},
            "plain",
        ]}]
        out = _summarize_messages(messages)
        assert out[0]["content"] == "[text] [image]"

    def test_non_dict_message_skipped(self):
        out = _summarize_messages(["string-entry", {"role": "user", "content": "x"}])
        assert len(out) == 1
        assert out[0]["role"] == "user"

    def test_truncation_and_last_six(self):
        messages = [{"role": "user", "content": "x" * 500} for _ in range(10)]
        out = _summarize_messages(messages)
        assert len(out) == 6  # last 6 only
        assert len(out[0]["content"]) == 300  # truncated


class TestHealerIntegration:
    def test_heal_with_llm_healer(self):
        def fake_healer(error, kwargs, provider, model):
            return ({"temperature": 0.1}, ["temperature"])
        rh = RequestHealer(rules=[], llm_healer=fake_healer)
        with patch.dict("os.environ", {"ATOM_LLM_HEALER_ENABLED": "true"}, clear=True):
            result = rh.heal(
                RuntimeError("400 bad request"), {"temperature": 0.9}, "p", "m")
        assert result.patched_kwargs == {"temperature": 0.1}
        assert result.rule == "llm"

    def test_heal_llm_healer_disabled(self):
        def fake_healer(error, kwargs, provider, model):
            return ({"temperature": 0.1}, ["temperature"])
        rh = RequestHealer(rules=[], llm_healer=fake_healer)
        with patch.dict("os.environ", {"ATOM_LLM_HEALER_ENABLED": "false"}, clear=True):
            result = rh.heal(RuntimeError("400 bad request"), {}, "p", "m")
        assert result.patched_kwargs is None

    def test_heal_llm_healer_raises(self):
        def fake_healer(error, kwargs, provider, model):
            raise RuntimeError("boom")
        rh = RequestHealer(rules=[], llm_healer=fake_healer)
        with patch.dict("os.environ", {"ATOM_LLM_HEALER_ENABLED": "true"}, clear=True):
            result = rh.heal(RuntimeError("400 bad request"), {}, "p", "m")
        assert result.patched_kwargs is None
