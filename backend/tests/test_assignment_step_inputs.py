import pytest

from core.assignment_plan import StepInputError, new_step


def _step(inputs):
    return new_step(
        step_id="send",
        title="Send the approved response",
        operation_type="outbound",
        adapter="email.send_outlook",
        inputs=inputs,
        effect="external",
        approval_required=True,
    )


def test_long_outbound_body_survives_step_sanitization():
    body = ("This is a long authorized outbound body.\n\n" * 80).strip()
    assert len(body) > 1000
    step = _step({"to": ["owner@example.invalid"], "subject": "S", "body": body})
    assert step["inputs"]["body"] == body


def test_exact_utf8_limit_is_preserved():
    body = "x" * 20_000
    step = _step({"to": ["owner@example.invalid"], "subject": "S", "body": body})
    assert step["inputs"]["body"] == body


def test_over_utf8_limit_is_rejected_before_planning():
    with pytest.raises(StepInputError, match="20000 UTF-8 bytes"):
        _step({"to": ["owner@example.invalid"], "subject": "S", "body": "x" * 20_001})


def test_multibyte_exact_limit_is_preserved():
    body = "é" * 10_000  # 20,000 UTF-8 bytes
    step = _step({"to": ["owner@example.invalid"], "subject": "S", "body": body})
    assert step["inputs"]["body"] == body


def test_multibyte_over_limit_is_rejected():
    body = "é" * 10_001  # 20,002 UTF-8 bytes
    with pytest.raises(StepInputError, match="20000 UTF-8 bytes"):
        _step({"to": ["owner@example.invalid"], "subject": "S", "body": body})


def test_collection_limit_is_rejected_not_truncated():
    with pytest.raises(StepInputError, match="10000 items"):
        _step({"rows": [["x"] for _ in range(10_001)]})


def test_nesting_limit_is_rejected_not_truncated():
    nested = "leaf"
    for _ in range(22):
        nested = {"n": nested}
    with pytest.raises(StepInputError, match="nesting"):
        _step({"payload": nested})
