"""Tests for the self-healing request healer (Feature 1 of the Manifest
gap-analysis work).

Covers: error classification, all 5 rule-based patches, the LLM-fallback
healer path (mocked), non-repairable passthrough, single-heal-cap semantics,
and rule exception-safety.
"""
from unittest.mock import MagicMock

import pytest

from core.llm.routing.request_healer import (
    HealingResult,
    RequestHealer,
    _DropResponseFormatRule,
    _DropTemperatureRule,
    _ParamRenameRule,
    _StripMultimodalRule,
    _TruncateContextRule,
    classify_error,
    get_request_healer,
    is_repairable,
)


class FakeStatusError(Exception):
    """Simulates openai.APIStatusError's .status_code attribute."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


# --- Error classification --------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected",
    [
        (FakeStatusError("bad request", 400), "repairable_4xx"),
        (FakeStatusError("not found", 404), "repairable_4xx"),
        (FakeStatusError("unprocessable", 422), "repairable_4xx"),
        (FakeStatusError("unauthorized", 401), "non_repairable_4xx"),
        (FakeStatusError("forbidden", 403), "non_repairable_4xx"),
        (FakeStatusError("rate limit", 429), "non_repairable_4xx"),
        (FakeStatusError("server error", 500), "server_error"),
        (FakeStatusError("bad gateway", 502), "server_error"),
        (FakeStatusError("timeout", 408), "transient"),
    ],
)
def test_classify_status_codes(exc, expected):
    assert classify_error(exc) == expected


def test_classify_substring_timeout():
    assert classify_error(Exception("the request timed out")) == "transient"


def test_classify_substring_rate_limit():
    assert classify_error(Exception("429 rate limit exceeded")) == "non_repairable_4xx"


def test_classify_substring_server_error():
    assert classify_error(Exception("503 service unavailable")) == "server_error"


def test_classify_substring_repairable():
    assert classify_error(Exception("400 bad request: max_tokens invalid")) == "repairable_4xx"


def test_classify_unknown():
    assert classify_error(Exception("something weird")) == "unknown"


def test_is_repairable_true_for_4xx():
    assert is_repairable(FakeStatusError("x", 400))
    assert is_repairable(FakeStatusError("x", 422))


def test_is_repairable_false_for_auth_and_server():
    assert not is_repairable(FakeStatusError("x", 401))
    assert not is_repairable(FakeStatusError("x", 500))


# --- Rule: param rename ---------------------------------------------------


def test_param_rename_matches_and_applies():
    rule = _ParamRenameRule()
    err = FakeStatusError("unexpected parameter: max_tokens is not supported", 400)
    kwargs = {"model": "gemini-1.5", "messages": [], "max_tokens": 1000}
    assert rule.matches(err, kwargs, "gemini", "gemini-1.5")
    patched, keys = rule.apply(kwargs)
    assert "max_tokens" not in patched
    assert patched["max_output_tokens"] == 1000
    assert "max_tokens->max_output_tokens" in keys


def test_param_rename_no_match_without_max_tokens():
    rule = _ParamRenameRule()
    err = FakeStatusError("unexpected parameter: max_tokens", 400)
    assert not rule.matches(err, {"model": "x", "messages": []}, "p", "m")


def test_param_rename_no_match_without_keyword():
    rule = _ParamRenameRule()
    err = FakeStatusError("some other error", 400)
    assert not rule.matches(err, {"max_tokens": 100}, "p", "m")


# --- Rule: drop temperature ------------------------------------------------


def test_drop_temperature_o_series():
    rule = _DropTemperatureRule()
    err = FakeStatusError("unsupported parameter: temperature", 400)
    kwargs = {"model": "o3-mini", "temperature": 0.7}
    assert rule.matches(err, kwargs, "openai", "o3-mini")
    patched, keys = rule.apply(kwargs)
    assert "temperature" not in patched
    assert keys == ["temperature"]


def test_drop_temperature_not_o_series():
    rule = _DropTemperatureRule()
    err = FakeStatusError("unsupported parameter: temperature", 400)
    # gpt-4o is not an o-series reasoning model — rule should not match.
    assert not rule.matches(err, {"model": "gpt-4o", "temperature": 0.7}, "openai", "gpt-4o")


def test_drop_temperature_no_temp_in_kwargs():
    rule = _DropTemperatureRule()
    err = FakeStatusError("unsupported parameter: temperature", 400)
    assert not rule.matches(err, {"model": "o3-mini"}, "openai", "o3-mini")


# --- Rule: strip multimodal ------------------------------------------------


def test_strip_multimodal():
    rule = _StripMultimodalRule()
    err = FakeStatusError("unsupported content type: image_url", 422)
    kwargs = {
        "model": "x",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "describe this"},
                    {"type": "image_url", "image_url": {"url": "data:..."}},
                ],
            }
        ],
    }
    assert rule.matches(err, kwargs, "p", "m")
    patched, keys = rule.apply(kwargs)
    assert isinstance(patched["messages"][0]["content"], str)
    assert "describe this" in patched["messages"][0]["content"]
    assert keys


def test_strip_multimodal_no_image():
    rule = _StripMultimodalRule()
    err = FakeStatusError("unsupported content type: image_url", 422)
    kwargs = {"model": "x", "messages": [{"role": "user", "content": "just text"}]}
    assert not rule.matches(err, kwargs, "p", "m")


def test_strip_multimodal_no_keyword():
    rule = _StripMultimodalRule()
    err = FakeStatusError("some other error", 400)
    kwargs = {"model": "x", "messages": [{"role": "user", "content": [{"type": "image_url"}]}]}
    assert not rule.matches(err, kwargs, "p", "m")


# --- Rule: truncate context ------------------------------------------------


def test_truncate_context():
    rule = _TruncateContextRule()
    err = FakeStatusError("This model's maximum context length is 8192 tokens", 400)
    kwargs = {
        "model": "x",
        "messages": [{"role": "system", "content": "sys"}]
        + [{"role": "user", "content": f"msg {i}"} for i in range(20)],
    }
    assert rule.matches(err, kwargs, "p", "m")
    patched, keys = rule.apply(kwargs)
    # System + last 4 user messages.
    assert len(patched["messages"]) == 5
    assert patched["messages"][0]["role"] == "system"
    assert keys


def test_truncate_context_already_short():
    rule = _TruncateContextRule()
    err = FakeStatusError("context length exceeded", 400)
    kwargs = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
    assert rule.matches(err, kwargs, "p", "m")
    patched, keys = rule.apply(kwargs)
    # Nothing to truncate — no change.
    assert keys == []


def test_truncate_context_no_match():
    rule = _TruncateContextRule()
    err = FakeStatusError("some other error", 400)
    kwargs = {"model": "x", "messages": [{"role": "user", "content": "hi"}]}
    assert not rule.matches(err, kwargs, "p", "m")


# --- Rule: drop response_format --------------------------------------------


def test_drop_response_format():
    rule = _DropResponseFormatRule()
    err = FakeStatusError("response_format is not supported", 400)
    kwargs = {"model": "x", "response_format": {"type": "json_object"}}
    assert rule.matches(err, kwargs, "p", "m")
    patched, keys = rule.apply(kwargs)
    assert "response_format" not in patched
    assert keys == ["response_format"]


def test_drop_response_format_no_match():
    rule = _DropResponseFormatRule()
    err = FakeStatusError("some other error", 400)
    assert not rule.matches(err, {"response_format": {}}, "p", "m")


# --- Healer end-to-end -----------------------------------------------------


def test_healer_rule_first_match_wins():
    healer = RequestHealer()
    # max_tokens error — param_rename should fire before other rules.
    err = FakeStatusError("unexpected parameter max_tokens", 400)
    r = healer.heal(err, {"model": "g", "messages": [], "max_tokens": 500}, "p", "m")
    assert r.patched_kwargs is not None
    assert r.rule == "param_rename_max_tokens"
    assert "max_output_tokens" in r.patched_kwargs


def test_healer_returns_none_for_non_repairable():
    healer = RequestHealer()
    r = healer.heal(FakeStatusError("unauthorized", 401), {"model": "g"}, "p", "m")
    assert r.patched_kwargs is None
    assert r.rule is None


def test_healer_returns_none_when_no_rule_matches():
    healer = RequestHealer()
    err = FakeStatusError("some weird 400 error we don't recognize", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert r.patched_kwargs is None
    assert r.rule is None


def test_healer_does_not_mutate_input_kwargs():
    healer = RequestHealer()
    err = FakeStatusError("max_tokens unsupported", 400)
    original = {"model": "g", "messages": [], "max_tokens": 500}
    original_copy = dict(original)
    healer.heal(err, original, "p", "m")
    assert original == original_copy  # input unchanged


# --- LLM fallback healer --------------------------------------------------


def test_llm_healer_off_by_default(monkeypatch):
    """Without ATOM_LLM_HEALER_ENABLED, the LLM healer is never called."""
    monkeypatch.delenv("ATOM_LLM_HEALER_ENABLED", raising=False)
    called = []

    def fake_llm_healer(error, kwargs, provider, model):
        called.append(True)
        return ({"model": "x", "messages": []}, ["model"])

    healer = RequestHealer(llm_healer=fake_llm_healer)
    # No rule matches, but error is repairable.
    err = FakeStatusError("weird 400", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert called == []  # LLM healer not invoked
    assert r.patched_kwargs is None


def test_llm_healer_invoked_when_enabled(monkeypatch):
    """With ATOM_LLM_HEALER_ENABLED=true and no rule match, LLM healer runs."""
    monkeypatch.setenv("ATOM_LLM_HEALER_ENABLED", "true")

    def fake_llm_healer(error, kwargs, provider, model):
        patched = dict(kwargs)
        patched["messages"] = [{"role": "user", "content": "fixed"}]
        return (patched, ["messages"])

    healer = RequestHealer(llm_healer=fake_llm_healer)
    err = FakeStatusError("weird 400", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert r.patched_kwargs is not None
    assert r.rule == "llm"
    assert "messages" in r.patched_keys


def test_llm_healer_returning_none_yields_no_patch(monkeypatch):
    monkeypatch.setenv("ATOM_LLM_HEALER_ENABLED", "true")
    healer = RequestHealer(llm_healer=lambda *a: None)
    err = FakeStatusError("weird 400", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert r.patched_kwargs is None


def test_llm_healer_exception_swallowed(monkeypatch):
    monkeypatch.setenv("ATOM_LLM_HEALER_ENABLED", "true")

    def raising_healer(*a):
        raise RuntimeError("healer exploded")

    healer = RequestHealer(llm_healer=raising_healer)
    err = FakeStatusError("weird 400", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert r.patched_kwargs is None  # exception swallowed, no patch


# --- Rule exception safety -------------------------------------------------


def test_rule_exception_does_not_break_healer():
    """If a rule's matches() raises, the healer skips it and continues."""

    class ExplodingRule:
        name = "exploding"
        def matches(self, *a):
            raise RuntimeError("boom")
        def apply(self, kwargs):
            return kwargs, []

    class WorkingRule:
        name = "working"
        def matches(self, error, kwargs, provider, model):
            return True
        def apply(self, kwargs):
            patched = dict(kwargs)
            patched["fixed"] = True
            return patched, ["fixed"]

    healer = RequestHealer(rules=[ExplodingRule(), WorkingRule()])
    err = FakeStatusError("400", 400)
    r = healer.heal(err, {"model": "g", "messages": []}, "p", "m")
    assert r.patched_kwargs is not None
    assert r.rule == "working"


# --- Singleton ------------------------------------------------------------


def test_get_request_healer_singleton():
    a = get_request_healer()
    b = get_request_healer()
    assert a is b


def test_healing_result_dataclass():
    r = HealingResult(patched_kwargs={"x": 1}, rule="test", patched_keys=["x"])
    assert r.patched_kwargs == {"x": 1}
    assert r.rule == "test"
    assert r.patched_keys == ["x"]
    r_none = HealingResult(patched_kwargs=None, rule=None)
    assert r_none.patched_kwargs is None
    assert r_none.patched_keys == []
