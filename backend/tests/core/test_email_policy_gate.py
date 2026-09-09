"""Unit tests for core.email_policy_gate — deterministic send-boundary rules.

Medium hygiene only (same-thread reply linkage) + the kill-switch/scoping
plumbing. Business rules are deliberately out of scope — see the module
docstring for why (they belong to per-workspace rule data, not code).
"""
import pytest

from core.email_policy_gate import (
    POLICY_NAME,
    active_rule_codes,
    blocked_payload,
    check_send_message,
    filter_violations,
    is_policy_enabled,
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
        "to": "new@b.com", "subject": "Introducing the company", "body": "Hello,",
    })
    assert violations == []


def test_blank_subject_new_email_passes():
    violations = check_send_message({"to": "a@b.com", "subject": "", "body": "x"})
    assert violations == []


# --- scope guard: business content is NOT judged ----------------------------


def test_price_in_body_is_not_gated():
    # Pricing rules were removed deliberately: what a verified price IS is a
    # per-business process (price list vs manual calculation vs approval
    # threshold). The transport gate must not judge business content.
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "thread_id": "t",
    })
    assert violations == []


def test_unavailable_statement_is_not_gated():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "That model is not available.",
        "thread_id": "t",
    })
    assert violations == []


def test_unknown_business_params_are_ignored_not_required():
    # No business vocabulary is advertised or required on the tool surface;
    # stray params an agent passes anyway must not affect the result.
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Hi,",
        "thread_id": "t",
        "price_verified": True, "item_model": "X", "customer_is_new": False,
        "company_name": "Y", "alternatives": ["Z"],
    })
    assert violations == []


# --- blocked payload shape ---------------------------------------------------


def test_blocked_payload_shape():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Hi",
    })
    payload = blocked_payload(violations)
    assert payload["status"] == "blocked"
    assert payload["blocked"] is True
    assert payload["policy"] == POLICY_NAME
    assert len(payload["violations"]) == 1
    assert all(v["fix"] for v in payload["violations"])


# --- kill switch + rule scoping ---------------------------------------------


def test_policy_enabled_by_default(monkeypatch):
    monkeypatch.delenv("ATOM_EMAIL_SEND_POLICY_ENABLED", raising=False)
    assert is_policy_enabled() is True


def test_policy_disabled_via_env(monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_SEND_POLICY_ENABLED", "false")
    assert is_policy_enabled() is False


def test_active_rules_none_when_unset(monkeypatch):
    monkeypatch.delenv("ATOM_EMAIL_SEND_POLICY_RULES", raising=False)
    assert active_rule_codes() is None


def test_active_rules_parsed_from_env(monkeypatch):
    monkeypatch.setenv("ATOM_EMAIL_SEND_POLICY_RULES", "reply_without_thread")
    assert active_rule_codes() == {"reply_without_thread"}


def test_filter_violations_keeps_all_when_no_scope():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Hi",
    })
    assert filter_violations(violations, None) == violations


def test_filter_violations_keeps_only_scoped_codes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "Hi",
    })
    scoped = filter_violations(violations, {"reply_without_thread"})
    assert [v["code"] for v in scoped] == ["reply_without_thread"]
    scoped2 = filter_violations(violations, {"some_future_rule"})
    assert scoped2 == []
