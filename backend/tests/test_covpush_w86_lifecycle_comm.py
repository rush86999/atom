# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/lifecycle_comm_generator (template gen, event phases).

LifecycleCommGenerator tested with the BYOK manager, DB session, and AI
service fully mocked (zero LLM spend):

- generate_draft: no workspace, workspace with business rules (formula vs
  value vs applies_to), no rules found, AI service present (with/without
  response key), AI service absent.
- _get_prompt_for_intent: request_quote, offer_quote, confirm_shipping,
  po_confirmation, and the generic fallback — each embedding the right
  context fields and JSON context.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.lifecycle_comm_generator import LifecycleCommGenerator


class _FakeSession:
    """Session whose query() returns a chainable filter ending in .all()."""

    def __init__(self, rows):
        self._rows = rows
        self.closed = False

    def query(self, model):
        return _Query(self._rows)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._rows


def _rule(description="Net 30", formula=None, value="30", applies_to="All"):
    r = MagicMock()
    r.description = description
    r.formula = formula
    r.value = value
    r.applies_to = applies_to
    return r


@pytest.fixture()
def generator():
    with patch("core.lifecycle_comm_generator.get_byok_manager", return_value=MagicMock()):
        yield LifecycleCommGenerator(ai_service=None)


# ---------------------------------------------------------------------------
# generate_draft
# ---------------------------------------------------------------------------

def test_generate_draft_no_ai_service(generator):
    result = asyncio.run(generator.generate_draft("request_quote", {"items": "widgets"}))
    assert result == "Thank you for your inquiry. We are processing your request."


def test_generate_draft_ai_service_response(generator):
    ai = MagicMock()
    ai.analyze_text = AsyncMock(return_value={"response": "Here is your quote draft."})
    gen = LifecycleCommGenerator(ai_service=ai)
    with patch("core.lifecycle_comm_generator.get_byok_manager", return_value=MagicMock()):
        result = asyncio.run(gen.generate_draft("request_quote", {"items": "widgets"}))

    assert result == "Here is your quote draft."
    prompt = ai.analyze_text.await_args.args[0]
    assert "Requesting a Quote" in prompt
    assert '"items": "widgets"' in prompt


def test_generate_draft_ai_service_missing_response_key(generator):
    ai = MagicMock()
    ai.analyze_text = AsyncMock(return_value={"other": "x"})
    gen = LifecycleCommGenerator(ai_service=ai)
    with patch("core.lifecycle_comm_generator.get_byok_manager", return_value=MagicMock()):
        result = asyncio.run(gen.generate_draft("request_quote", {}))

    assert result == "I'll look into this for you."


def test_generate_draft_with_business_rules():
    fake = _FakeSession([_rule(), _rule(description="Overtime", formula="hours*1.5", applies_to=None)])
    ai = MagicMock()
    ai.analyze_text = AsyncMock(return_value={"response": "draft"})
    gen = LifecycleCommGenerator(ai_service=ai)
    with patch("core.lifecycle_comm_generator.get_byok_manager", return_value=MagicMock()):
        with patch("core.lifecycle_comm_generator.get_db_session", return_value=fake):
            result = asyncio.run(gen.generate_draft(
                "request_quote", {"items": "x"}, workspace_id="ws-1"
            ))

    assert result == "draft"
    prompt = ai.analyze_text.await_args.args[0]
    assert "Applicable Business Rules & Calculations" in prompt
    assert "Net 30: 30 (Applies to: All)" in prompt
    assert "Overtime: hours*1.5 (Applies to: General)" in prompt
    assert fake.closed is True


def test_generate_draft_no_rules_found():
    fake = _FakeSession([])
    ai = MagicMock()
    ai.analyze_text = AsyncMock(return_value={"response": "draft"})
    gen = LifecycleCommGenerator(ai_service=ai)
    with patch("core.lifecycle_comm_generator.get_byok_manager", return_value=MagicMock()):
        with patch("core.lifecycle_comm_generator.get_db_session", return_value=fake):
            result = asyncio.run(gen.generate_draft(
                "request_quote", {"items": "x"}, workspace_id="ws-1"
            ))
    assert result == "draft"
    prompt = ai.analyze_text.await_args.args[0]
    assert "Applicable Business Rules" not in prompt


# ---------------------------------------------------------------------------
# _get_prompt_for_intent
# ---------------------------------------------------------------------------

def test_prompt_request_quote(generator):
    prompt = generator._get_prompt_for_intent("request_quote", {"items": "Widgets"})
    assert "Requesting a Quote" in prompt
    assert "Widgets" in prompt
    assert "pricing, availability, and terms" in prompt


def test_prompt_offer_quote(generator):
    prompt = generator._get_prompt_for_intent(
        "offer_quote", {"quote_details": "$500", "customer_name": "Acme"}
    )
    assert "Offering a Quote" in prompt
    assert "$500" in prompt
    assert "Acme" in prompt


def test_prompt_confirm_shipping(generator):
    prompt = generator._get_prompt_for_intent(
        "confirm_shipping", {"tracking_number": "1Z999", "carrier": "UPS", "est_delivery": "Fri"}
    )
    assert "Shipment Confirmation" in prompt
    assert "1Z999" in prompt
    assert "UPS" in prompt
    assert "Fri" in prompt


def test_prompt_po_confirmation(generator):
    prompt = generator._get_prompt_for_intent(
        "po_confirmation", {"po_id": "PO-42", "total_amount": "$1,200"}
    )
    assert "Purchase Order Confirmation" in prompt
    assert "PO-42" in prompt
    assert "$1,200" in prompt


def test_prompt_generic_fallback(generator):
    prompt = generator._get_prompt_for_intent("payment_reminder", {"amount": 99})
    assert "professional, concise email" in prompt
    assert '"amount": 99' in prompt
