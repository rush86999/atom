"""Negative tests for the structured-failure AUTH-FAILURE memo classification.

Background (acceptance rig 2026-09-28): the memo condition used a bare
``"401" in err_str`` substring scan, but the marshalled instructor error
embeds the full completion repr — ids, millisecond timestamps, token counts —
so a numeric echo benched a healthy provider as ``invalid_credential`` for
600 s and every later forked leg failed. A standalone ``401`` inside
arbitrary completion text is NOT an HTTP authentication failure: the memo
must classify from structured exception/status information
(``model_route_registry._status_of``: status_code attr → response status →
status-bearing wording only), never from a bare number in the echo.
"""
from __future__ import annotations

import pytest

from core.llm.model_route_registry import (
    FailureCause,
    _status_of,
    classify_failure,
)


class _FakeAPIStatusError(Exception):
    """Mimics openai.APIStatusError's structured surface."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _instructor_style_error() -> Exception:
    """The marshalled instructor validation error shape seen in the rig:
    the echoed ChatCompletion repr carries ms timestamps and numeric ids."""
    return Exception(
        "No tool calls or function call found in response (mode: TOOLS). "
        "Validation Error found:\n<failed_attempts>\n"
        "<generation number=\"1\">\n<exception>\n"
        "    No tool calls or function call found in response (mode: TOOLS)\n"
        "</exception>\n<completion>\n"
        "    ChatCompletion(id='shim-1790621440094-401', "
        "created=1790621440094401, "
        "usage=CompletionUsage(prompt_tokens=1401, completion_tokens=4012, "
        "total_tokens=5413), system_fingerprint='fp_401')\n"
        "</completion>\n</generation>\n</failed_attempts>"
    )


def test_standalone_401_in_completion_text_is_not_credential_failure():
    """Arbitrary '401' tokens inside the echoed completion repr must not
    classify as an authentication failure."""
    exc = _instructor_style_error()
    assert _status_of(exc) is None, (
        "structured status extraction must not read a bare number out of "
        "the echoed completion repr")
    cause, _, _ = classify_failure(exc=exc)
    assert cause != FailureCause.INVALID_CREDENTIAL


def test_structured_status_401_is_credential_failure():
    exc = _FakeAPIStatusError(401, "Incorrect API key provided")
    assert _status_of(exc) == 401
    cause, _, _ = classify_failure(exc=exc, status=401)
    assert cause == FailureCause.INVALID_CREDENTIAL


def test_status_bearing_text_is_credential_failure():
    """When structure is lost, only status-BEARING wording may classify:
    'Error code: 401' is a status; 'order 401 shipped' is not."""
    exc = Exception("Error code: 401 - Incorrect API key provided")
    assert _status_of(exc) == 401

    plain = Exception("Your order 401 has shipped and 401 units arrived")
    assert _status_of(plain) is None
    cause, _, _ = classify_failure(exc=plain)
    assert cause != FailureCause.INVALID_CREDENTIAL


def test_memo_condition_composition_matches_structured_rule():
    """The exact predicate the AUTH-FAILURE memo applies: structured status
    in (401, 403), or explicit credential wording — never a bare scan."""
    def memo_would_fire(exc: BaseException, err_str: str) -> bool:
        status = _status_of(exc)
        return (
            status in (401, 403)
            or "autherror" in err_str.lower()
            or "invalid api key" in err_str.lower()
        )

    echo = _instructor_style_error()
    assert memo_would_fire(echo, str(echo)) is False
    assert memo_would_fire(
        _FakeAPIStatusError(401, "wrong key"), str(echo)) is True
    assert memo_would_fire(
        _FakeAPIStatusError(403, "forbidden"), "") is True
    # Explicit wording without structure still fires (deliberate: it is
    # credential wording, not a number).
    assert memo_would_fire(
        Exception("provider said: invalid api key"), "invalid api key") is True
