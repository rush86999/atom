"""Legacy nested-draft precedence for email canvas content.

The read-side view treats a present canonical top-level key as authoritative
(``_email_visible_view``); the general normalizer must agree. A nested
``draft`` is legacy metadata and may only supply keys that are ABSENT. An
explicit empty top-level ``to``/``cc``/``subject``/``body`` is a value, not a
reason to resurrect stale draft data.
"""
from core.chat_draft_classifier import (
    coerce_email_canvas,
    normalize_email_content,
)

STALE_DRAFT = {
    "draft_id": "draft-legacy-1",
    "to_emails": ["old@example.invalid"],
    "cc_emails": ["oldcc@example.invalid"],
    "subject": "Email Draft OLD",
    "body": "Old body OLD-1111",
    "attachments": [{"attachment_id": "att-old"}],
}

CURRENT = {
    "to": "alpha@example.invalid, clear@example.invalid",
    "cc": "",
    "subject": "Email Draft CURRENT",
    "body": "Current body NEW-EMAIL-7788",
    "attachments": [],
    "thread_id": "thread-7742",
    "source_message_id": "<source-7742@example.invalid>",
    "imported_from": "sender@example.invalid",
    "draft": STALE_DRAFT,
}


def test_top_level_fields_win_over_stale_nested_draft():
    result = normalize_email_content(dict(CURRENT))
    assert result["to"] == "alpha@example.invalid, clear@example.invalid"
    assert result["cc"] == ""
    assert result["subject"] == "Email Draft CURRENT"
    assert result["body"] == "Current body NEW-EMAIL-7788"


def test_top_level_wins_with_explicit_empty_values():
    content = {
        "to": "",
        "cc": "",
        "subject": "",
        "body": "",
        "draft": dict(STALE_DRAFT),
    }
    result = normalize_email_content(content)
    assert result["to"] == ""
    assert result["cc"] == ""
    assert result["subject"] == ""
    assert result["body"] == ""


def test_legacy_only_draft_still_resolves():
    result = normalize_email_content({"draft": dict(STALE_DRAFT)})
    assert result["to"] == "old@example.invalid"
    assert result["cc"] == "oldcc@example.invalid"
    assert result["subject"] == "Email Draft OLD"
    assert result["body"] == "Old body OLD-1111"


def test_provenance_and_draft_identity_are_preserved():
    result = normalize_email_content(dict(CURRENT))
    assert result["thread_id"] == "thread-7742"
    assert result["source_message_id"] == "<source-7742@example.invalid>"
    assert result["imported_from"] == "sender@example.invalid"
    assert result["draft"]["draft_id"] == "draft-legacy-1"
    # The nested canonical view is refreshed, not left stale.
    assert result["draft"]["to_emails"] == [
        "alpha@example.invalid", "clear@example.invalid"]
    assert result["draft"]["cc_emails"] == []
    assert result["draft"]["subject"] == "Email Draft CURRENT"
    assert result["draft"]["body"] == "Current body NEW-EMAIL-7788"


def test_normalization_is_idempotent():
    once = normalize_email_content(dict(CURRENT))
    twice = normalize_email_content(once)
    assert once == twice

    empty = {"to": "", "cc": "", "subject": "", "body": "", "draft": dict(STALE_DRAFT)}
    empty_once = normalize_email_content(empty)
    assert empty_once == normalize_email_content(empty_once)

    legacy_once = normalize_email_content({"draft": dict(STALE_DRAFT)})
    assert legacy_once == normalize_email_content(legacy_once)


def test_list_recipients_are_canonicalized():
    result = normalize_email_content({
        "to": ["a@example.invalid", "b@example.invalid"],
        "cc": [],
        "subject": "S",
        "body": "B",
    })
    assert result["to"] == "a@example.invalid, b@example.invalid"
    assert result["cc"] == ""


def test_coerce_uses_the_same_precedence():
    ctype, content = coerce_email_canvas("email", dict(CURRENT))
    assert ctype == "email"
    assert content["subject"] == "Email Draft CURRENT"
    assert content["cc"] == ""
    assert content["draft"]["body"] == "Current body NEW-EMAIL-7788"
