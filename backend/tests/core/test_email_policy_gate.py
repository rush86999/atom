"""Unit tests for core.email_policy_gate — deterministic send-boundary rules.

Level B: same-thread + price-verification + specs + alternatives +
customer-intro enforcement, all LLM-free.
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
        "item_model": "SR48P",
    })
    assert [v["code"] for v in violations] == ["unverified_price"]
    assert violations[0]["rule"] == "price_verification"


def test_rupee_price_without_verification_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote",
        "body": "Price: \u20b92,400 for the shear.", "item_model": "shear-900",
    })
    assert "unverified_price" in [v["code"] for v in violations]


def test_price_with_verified_true_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": True, "price_source": "price list email",
        "item_model": "SR48P",
    })
    assert violations == []


def test_price_with_string_true_passes():
    # LLM tool callers pass strings — tolerate them.
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": "true", "item_model": "SR48P",
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
        "item_model": "SR48P",
    })
    codes = {v["code"] for v in violations}
    assert codes == {"reply_without_thread", "unverified_price"}


# --- specs rule (quote_without_item) --------------------------------------


def test_price_without_item_model_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": True,
    })
    assert [v["code"] for v in violations] == ["quote_without_item"]
    assert violations[0]["rule"] == "missing_details"


def test_price_with_item_model_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Quote", "body": "It is $1,250.",
        "price_verified": True, "item_model": "SR48P",
    })
    assert violations == []


# --- alternatives rule ------------------------------------------------------


def test_unavailable_without_alternatives_is_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P", "body": "That model is not available.",
        "thread_id": "t",
    })
    assert [v["code"] for v in violations] == ["unavailable_without_alternatives"]
    assert violations[0]["rule"] == "offer_alternatives"


def test_unavailable_with_alternatives_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P", "body": "SR48P is not available.",
        "thread_id": "t",
        "alternatives": ["SR50P", "SR60 series"],
    })
    assert violations == []


def test_unavailable_with_alternatives_text_passes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "We no longer carry it, but the SR50P is a comparable option.",
        "thread_id": "t",
        "alternatives": "SR50P",
    })
    assert violations == []


def test_positive_availability_not_blocked():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P", "body": "We have it in stock.",
        "thread_id": "t",
    })
    assert violations == []


# --- customer intro rule ----------------------------------------------------


def test_new_customer_without_company_name_is_blocked():
    violations = check_send_message({
        "to": "new@b.com", "subject": "Re: quote", "body": "Hi,",
        "thread_id": "t", "customer_is_new": True,
    })
    assert [v["code"] for v in violations] == ["new_customer_without_intro"]
    assert violations[0]["rule"] == "customer_intro"


def test_new_customer_company_not_in_body_is_blocked():
    violations = check_send_message({
        "to": "new@b.com", "subject": "Re: quote",
        "body": "Hi, thanks for your interest.", "thread_id": "t",
        "customer_is_new": True, "company_name": "Brennan Machinery",
    })
    assert "new_customer_without_intro" in [v["code"] for v in violations]


def test_new_customer_with_intro_passes():
    violations = check_send_message({
        "to": "new@b.com", "subject": "Re: quote",
        "body": "Thanks for reaching out to Brennan Machinery Inc.",
        "thread_id": "t",
        "customer_is_new": True, "company_name": "Brennan Machinery",
    })
    assert violations == []


def test_existing_customer_needs_no_intro():
    violations = check_send_message({
        "to": "old@b.com", "subject": "Re: quote", "body": "Hi,",
        "thread_id": "t", "customer_is_new": False,
    })
    assert violations == []


def test_string_true_customer_flag_tolerated():
    violations = check_send_message({
        "to": "new@b.com", "subject": "Re: quote",
        "body": "Welcome to Brennan Machinery.",
        "thread_id": "t",
        "customer_is_new": "true", "company_name": "Brennan Machinery",
    })
    assert violations == []


# --- golden path + combined payload -----------------------------------------


def test_full_compliant_quote_reply_passes():
    """A fully compliant quote reply: threaded + verified price + item +
    alternatives-not-needed + existing customer."""
    violations = check_send_message({
        "subject": "Re: Quote for SR48P",
        "thread_id": "t-1",
        "body": "The SR48P shear is $1,250 and in stock. Thanks!",
        "price_verified": True,
        "price_source": "Brennan Machinery Price List",
        "item_model": "SR48P",
        "customer_is_new": False,
    })
    assert violations == []


def test_blocked_payload_shape():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "It costs $5.",
        "item_model": "SR48P",
    })
    payload = blocked_payload(violations)
    assert payload["status"] == "blocked"
    assert payload["blocked"] is True
    assert payload["policy"] == POLICY_NAME
    assert len(payload["violations"]) == 2
    assert all(v["fix"] for v in payload["violations"])


# --- data-backed rules (catalog + known customers) --------------------------

CATALOG = ["SR48P", "PH-52", "50514-EC", "EN100"]


def test_alternatives_not_in_catalog_is_blocked_when_catalog_known():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "SR48P is not available.",
        "thread_id": "t",
        "alternatives": ["Bogus-9000"],
    }, catalog=CATALOG)
    assert [v["code"] for v in violations] == ["alternatives_not_in_catalog"]


def test_alternatives_from_catalog_pass():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "SR48P is not available, but the PH-52 is a comparable shear.",
        "thread_id": "t",
        "alternatives": ["PH-52"],
    }, catalog=CATALOG)
    assert violations == []


def test_alternatives_match_is_case_insensitive():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "SR48P is not available.",
        "thread_id": "t",
        "alternatives": ["ph-52"],
    }, catalog=CATALOG)
    assert violations == []


def test_empty_catalog_keeps_param_contract():
    # No catalog seeded => alternatives are not DB-verifiable; only the
    # presence check applies (backward compatible with unseeded workspaces).
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: SR48P",
        "body": "SR48P is not available.",
        "thread_id": "t",
        "alternatives": ["Whatever-1"],
    }, catalog=())
    assert violations == []


def test_known_customer_marked_new_is_blocked():
    violations = check_send_message({
        "to": "buyer.one@example.com", "subject": "Re: quote", "body": "Hi,",
        "thread_id": "t",
        "customer_is_new": True,
        "company_name": "Brennan Machinery",
        # body does NOT mention the company, but the mismatch rule should
        # fire first and short-circuit the intro requirement.
    }, known_customers=["buyer.one@example.com"])
    assert [v["code"] for v in violations] == ["customer_already_known"]


def test_recipient_from_to_recipients_dict_form():
    violations = check_send_message({
        "to_recipients": [{"emailAddress": {"address": "buyer.one@example.com"}}],
        "subject": "Re: quote", "body": "Hi,",
        "thread_id": "t",
        "customer_is_new": True,
    }, known_customers=["buyer.one@example.com"])
    assert [v["code"] for v in violations] == ["customer_already_known"]


def test_unknown_recipient_with_intro_passes_with_data_context():
    violations = check_send_message({
        "to": "brand-new@customer.com", "subject": "Re: quote",
        "body": "Thanks for reaching out to Brennan Machinery Inc.",
        "thread_id": "t",
        "customer_is_new": True,
        "company_name": "Brennan Machinery",
    }, known_customers=["buyer.one@example.com"])
    assert violations == []


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
    monkeypatch.setenv("ATOM_EMAIL_SEND_POLICY_RULES", "unverified_price,quote_without_item")
    assert active_rule_codes() == {"unverified_price", "quote_without_item"}


def test_filter_violations_keeps_all_when_no_scope():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "It costs $5.",
        "item_model": "SR48P",
    })
    assert filter_violations(violations, None) == violations


def test_filter_violations_keeps_only_scoped_codes():
    violations = check_send_message({
        "to": "a@b.com", "subject": "Re: quote", "body": "It costs $5.",
        "item_model": "SR48P",
    })
    scoped = filter_violations(violations, {"quote_without_item"})
    assert scoped == []
    scoped2 = filter_violations(violations, {"reply_without_thread"})
    assert [v["code"] for v in scoped2] == ["reply_without_thread"]
