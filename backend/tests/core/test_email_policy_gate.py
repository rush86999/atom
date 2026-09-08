"""Unit tests for core.email_policy_gate — deterministic send-boundary rules.

Level B (minimal): same-thread + price-verification enforcement, LLM-free.
"""
import pytest

from core.email_policy_gate import (
    blocked_payload,
    check_send_message,
    POLICY_NAME,
)


# --- same-thread rule -----------------------------------------------------


def test_reply_subject_without_thread_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: Quote for SR48P", "body": "Hi,",
    })
    assert [v["code"] for v in violations] == ["reply_without_thread"]
    assert violations[0]["rule"] == "same_thread"


def test_fwd_prefix_without_thread_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Fwd: machine list", "body": "see below",
    })
    assert "reply_without_thread" in [v["code"] for v in violations]


def test_reply_subject_with_thread_id_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: Quote for SR48P", "body": "Hi,",
        "thread_id": "12345",
    })
    assert violations == []


def test_reply_subject_with_reply_to_message_id_passes():
    violations = check_send_message({
        "subject": "Re: shears", "body": "Hi,",
        "reply_to_message_id": "msg-1",
    })
    assert violations == []


def test_conversation_id_counts_as_linkage():
    violations = check_send_message({
        "to": "a@b.com", "subject": "RE: quote", "body": "Hi,",
        "conversation_id": "conv-9",
    })
    assert violations == []


def test_message_id_counts_as_linkage():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Hi,",
        "message_id": "m-9",
    })
    assert violations == []


def test_new_email_without_reply_prefix_passes():
    violations = check_send_message({
        "to": "new@b.com", "subject": "Introducing Brennan Machinery", "body": "Hello,",
    })
    assert violations == []


def test_blank_subject_new_email_passes():
    violations = check_send_message({"to": "a@b.com", "subject": "", "body": "x"})
    assert violations == []


# --- price-verification rule ----------------------------------------------


def test_price_in_body_without_verification_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "The SR48P is $1,250 plus tax.",
    })
    assert [v["code"] for v in violations] == ["unverified_price"]
    assert violations[0]["rule"] == "price_verification"


def test_rupee_price_without_verification_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "Price: \u20b92,400 for the shear.",
    })
    assert "unverified_price" in [v["code"] for v in violations]


def test_price_with_verified_true_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": True, "price_source": "price list email",
    })
    assert violations == []


def test_price_with_string_true_passes():
    # LLM tool callers pass strings — tolerate them.
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": "true",
    })
    assert violations == []


def test_no_price_in_body_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "We have the SR48P in stock.",
    })
    assert violations == []


def test_bare_model_number_does_not_trigger_price():
    # No currency marker => not a price claim.
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P", "body": "Model 5000 available.",
        "thread_id": "t",
    })
    assert violations == []


def test_both_violations_reported_together():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Price is $800.",
    })
    codes = {v["code"] for v in violations}
    assert codes == {"reply_without_thread", "unverified_price"}


# --- blocked payload -------------------------------------------------------


def test_blocked_payload_shape():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "It costs $5.",
    })
    payload = blocked_payload(violations)
    assert payload["status"] == "blocked"
    assert payload["blocked"] is True
    assert payload["policy"] == POLICY_NAME
    assert len(payload["violations"]) == 2
    assert all(v["fix"] for v in payload["violations"])
