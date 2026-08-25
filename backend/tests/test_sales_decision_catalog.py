"""
Sales decision-catalog builder tests — the business-discovery step.

The catalog classifier turns historical customer emails into structured
(Situation -> Action -> Human?) rows the future sales agent can consult.
These tests pin the prompt builder, the robust JSON parser, the classify
wrapper, and the aggregation into the decision table.
"""

import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, patch

from core.sales_decision_catalog import (
    build_classification_prompt,
    parse_classification,
    classify_email,
    aggregate_catalog,
)

SAMPLE_EMAIL = {
    "subject": "Quote Request - Press Brake",
    "body_preview": "Need a quote for a 100-ton press brake.",
    "body": {
        "content": (
            "Hi, we need a 100-ton press brake with a 10ft bed. "
            "Please send pricing and lead time."
        )
    },
    "from_field": {"emailAddress": {"name": "Jane Smith", "address": "jane@acme.example"}},
    "received_date_time": "2026-08-20T10:00:00Z",
}


# --------------------------------------------------------------------------- #
# build_classification_prompt (pure)
# --------------------------------------------------------------------------- #

def test_prompt_includes_email_fields():
    prompt = build_classification_prompt(SAMPLE_EMAIL)
    assert "Jane Smith" in prompt
    assert "jane@acme.example" in prompt
    assert "Quote Request - Press Brake" in prompt
    assert "100-ton press brake" in prompt
    for dim in (
        "intent", "customer_question", "sales_action", "info_needed",
        "systems_checked", "people_contacted", "decision_reason",
        "exception", "outcome", "needs_human", "business_rule",
    ):
        assert dim in prompt


def test_prompt_handles_body_dict_and_missing_fields():
    email = {"subject": "Hi", "body": None}
    prompt = build_classification_prompt(email)
    assert "Hi" in prompt


# --------------------------------------------------------------------------- #
# parse_classification (robust JSON extraction)
# --------------------------------------------------------------------------- #

def test_parse_classification_plain_json():
    raw = '{"intent": "request_quote", "sales_action": "prepare_quote", "needs_human": false}'
    out = parse_classification(raw)
    assert out["intent"] == "request_quote"
    assert out["sales_action"] == "prepare_quote"
    assert out["needs_human"] is False


def test_parse_classification_fenced_json():
    raw = 'Sure, here is the result:\n```json\n{"intent": "service_call", "needs_human": true}\n```'
    out = parse_classification(raw)
    assert out["intent"] == "service_call"
    assert out["needs_human"] is True


def test_parse_classification_truncated_salvage():
    # Missing closing brace — parser must still recover a usable dict.
    raw = '{"intent": "request_quote", "sales_action": "check_inventory", "needs_human": fals'
    out = parse_classification(raw)
    assert out["intent"] == "request_quote"
    assert out["sales_action"] == "check_inventory"


def test_parse_classification_unparseable_returns_empty_defaults():
    out = parse_classification("I have no idea what you want.")
    assert out["intent"] == "unknown"
    assert out["needs_human"] is False
    assert out["business_rule"] == ""


def test_parse_classification_fills_missing_keys():
    out = parse_classification('{"intent": "hi"}')
    assert out["intent"] == "hi"
    assert out["sales_action"] == ""
    assert out["needs_human"] is False


# --------------------------------------------------------------------------- #
# classify_email (async wrapper)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_classify_email_uses_call_llm_and_parses():
    async def fake_call(prompt, system_instruction):
        assert "Jane" in prompt
        return '{"intent": "request_quote", "sales_action": "check_inventory"}'

    out = await classify_email(SAMPLE_EMAIL, call_llm=fake_call)
    assert out["intent"] == "request_quote"
    assert out["sales_action"] == "check_inventory"


@pytest.mark.asyncio
async def test_classify_email_empty_llm_result_is_unknown():
    async def fake_call(prompt, system_instruction):
        return ""

    out = await classify_email(SAMPLE_EMAIL, call_llm=fake_call)
    assert out["intent"] == "unknown"


# --------------------------------------------------------------------------- #
# aggregate_catalog (decision table)
# --------------------------------------------------------------------------- #

def test_aggregate_catalog_groups_by_rule():
    classifications = [
        {"intent": "request_quote", "sales_action": "check_inventory",
         "needs_human": False, "business_rule": "standard machine + stock",
         "exception": "", "systems_checked": ["zoho_inventory"], "subject": "A"},
        {"intent": "request_quote", "sales_action": "check_inventory",
         "needs_human": True, "business_rule": "standard machine + stock",
         "exception": "CSA unknown", "systems_checked": ["zoho_inventory"], "subject": "B"},
        {"intent": "service_call", "sales_action": "ask_human",
         "needs_human": True, "business_rule": "service call",
         "exception": "", "systems_checked": [], "subject": "C"},
    ]
    rows = aggregate_catalog(classifications)
    assert len(rows) == 2
    by_rule = {r["rule"]: r for r in rows}
    std = by_rule["standard machine + stock"]
    assert std["count"] == 2
    assert std["needs_human"] is True  # majority / any human -> human row
    assert "CSA unknown" in std["exceptions"]
    svc = by_rule["service call"]
    assert svc["count"] == 1
    assert svc["needs_human"] is True


def test_aggregate_catalog_empty():
    assert aggregate_catalog([]) == []


def test_aggregate_catalog_sorts_by_count_desc():
    classifications = [
        {"intent": "a", "sales_action": "x", "needs_human": False,
         "business_rule": "r1", "exception": "", "systems_checked": [], "subject": "s1"},
        {"intent": "b", "sales_action": "y", "needs_human": False,
         "business_rule": "r2", "exception": "", "systems_checked": [], "subject": "s2"},
        {"intent": "b", "sales_action": "y", "needs_human": False,
         "business_rule": "r2", "exception": "", "systems_checked": [], "subject": "s3"},
    ]
    rows = aggregate_catalog(classifications)
    assert rows[0]["rule"] == "r2"
    assert rows[1]["rule"] == "r1"
