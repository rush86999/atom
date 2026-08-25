"""
Outlook Automation LLM draft tests.

The automation loop used a fixed reply template for Brennan contact-page
quote requests. These tests pin the new behavior: when ATOM_OUTLOOK_LLM_DRAFTS
is enabled, the HITL approval carries an LLM-drafted reply grounded in the
customer's email; on any LLM failure/timeout it degrades to the template and
never raises.
"""

import asyncio
import os

os.environ.setdefault("TESTING", "1")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import outlook_automation_service as oas
from outlook_automation_service import _draft_reply, _build_draft_prompt

MATCHING_EMAIL = {
    "id": "real_email_1",
    "subject": "Quote Request - Press Brake",
    "body_preview": "Hi, I visited https://brennan.ca/pages/contact. Need a quote.",
    "body": {
        "contentType": "text",
        "content": "Hi, I visited https://brennan.ca/pages/contact. "
                   "Please quote a 100-ton press brake for our shop.",
    },
    "from_field": {
        "emailAddress": {"name": "Jane Smith", "address": "jane@acme.example"}
    },
}


class FakeQuery:
    def __init__(self, first_value=None, all_value=None):
        self._first = first_value
        self._all = all_value

    def filter(self, *a, **k):
        return self

    def like(self, *a, **k):
        return self

    def first(self):
        return self._first

    def all(self):
        return self._all if self._all is not None else []


class FakeSession:
    def __init__(self):
        self.queries = []
        self.committed = False
        self.closed = False

    def query(self, *a, **k):
        return FakeQuery()

    def add(self, *a, **k):
        pass

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class FakeLLM:
    def __init__(self, text="Thanks for your interest! I will get you the quote."):
        self.text = text
        self.raise_error = False
        self.sleep = 0.0

    async def generate(self, *a, **k):
        if self.sleep:
            await asyncio.sleep(self.sleep)
        if self.raise_error:
            raise RuntimeError("provider down")
        return self.text


# --------------------------------------------------------------------------- #
# _build_draft_prompt (pure)
# --------------------------------------------------------------------------- #

def test_build_draft_prompt_includes_email_and_sender():
    prompt = _build_draft_prompt(
        sender_name="Jane Smith",
        sender_email="jane@acme.example",
        subject="Quote Request - Press Brake",
        body="Please quote a 100-ton press brake.",
        preview="Need a quote.",
    )
    assert "Jane Smith" in prompt
    assert "jane@acme.example" in prompt
    assert "Quote Request - Press Brake" in prompt
    assert "100-ton press brake" in prompt
    assert "Brennan Machinery" in prompt


# --------------------------------------------------------------------------- #
# _draft_reply (async, fault-isolated)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
async def test_draft_reply_returns_llm_generated_text():
    llm = FakeLLM("Your drafted reply body")
    with patch.object(oas, "get_llm_service", return_value=llm):
        out = await _draft_reply(
            "Jane Smith", "jane@acme.example", "Quote Request",
            "Please quote a press brake.", "preview",
        )
    assert out == "Your drafted reply body"


@pytest.mark.asyncio
async def test_draft_reply_trims_whitespace():
    llm = FakeLLM("  \n  Drafted body.  \n")
    with patch.object(oas, "get_llm_service", return_value=llm):
        out = await _draft_reply("Jane", "j@x.com", "S", "B", "p")
    assert out == "Drafted body."


@pytest.mark.asyncio
async def test_draft_reply_returns_empty_on_llm_error():
    llm = FakeLLM()
    llm.raise_error = True
    with patch.object(oas, "get_llm_service", return_value=llm):
        out = await _draft_reply("Jane", "j@x.com", "S", "B", "p")
    assert out == ""


@pytest.mark.asyncio
async def test_draft_reply_returns_empty_on_timeout():
    llm = FakeLLM()
    llm.sleep = 30  # longer than the 5s cap
    with patch.object(oas, "get_llm_service", return_value=llm):
        out = await asyncio.wait_for(
            _draft_reply("Jane", "j@x.com", "S", "B", "p"), timeout=15
        )
    assert out == ""


# --------------------------------------------------------------------------- #
# _matches_email_trigger (widened trigger: contact URL OR quote keywords)
# --------------------------------------------------------------------------- #

def test_trigger_matches_contact_url():
    assert oas._matches_email_trigger("please see https://brennan.ca/pages/contact thanks")


def test_trigger_matches_quote_keyword():
    assert oas._matches_email_trigger("Can you send me a quote for 5 sheets?")


def test_trigger_matches_price_keyword():
    assert oas._matches_email_trigger("What is your price on the press brake?")


def test_trigger_matches_case_insensitive():
    assert oas._matches_email_trigger("Please send PRICE list")


def test_trigger_matches_pricing_and_estimate():
    assert oas._matches_email_trigger("Need pricing and an estimate please")


def test_trigger_ignores_unrelated_email():
    assert not oas._matches_email_trigger("Hi, can we reschedule our meeting to Thursday?")


def test_trigger_respects_env_keyword_override(monkeypatch):
    monkeypatch.setenv("ATOM_OUTLOOK_TRIGGER_KEYWORDS", "catalog,brochure")
    assert oas._matches_email_trigger("Send me your catalog")
    assert not oas._matches_email_trigger("Send me a quote")


# --------------------------------------------------------------------------- #
# _looks_like_failure (reject error-shaped LLM output as a draft)
# --------------------------------------------------------------------------- #

def test_looks_like_failure_detects_known_markers():
    assert oas._looks_like_failure(
        "I'm sorry, I couldn't generate a response. Please check your API key configuration in Settings or try again."
    )
    assert oas._looks_like_failure("All providers failed. Last error: Error code: 401")
    assert oas._looks_like_failure("Insufficient balance. Manage your billing here: ...")


def test_looks_like_failure_ok_for_normal_draft():
    assert not oas._looks_like_failure(
        "Thanks for your quote request! We will send you a formal quote for the 100-ton press brake shortly."
    )


@pytest.mark.asyncio
async def test_draft_reply_rejects_error_shaped_output():
    llm = FakeLLM(
        "I'm sorry, I couldn't generate a response. Please check your API key configuration in Settings or try again."
    )
    with patch.object(oas, "get_llm_service", return_value=llm):
        out = await _draft_reply("Jane", "j@x.com", "S", "B", "p")
    assert out == ""


# --------------------------------------------------------------------------- #
# process_outlook_automation wiring
# --------------------------------------------------------------------------- #

def _patch_process(monkeypatch, emails=None, draft="", flag="true", existing_hitl=None):
    monkeypatch.setenv("ATOM_OUTLOOK_LLM_DRAFTS", flag)
    session = FakeSession()
    monkeypatch.setattr(oas, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        oas.outlook_service, "get_unread_emails",
        AsyncMock(return_value=emails or []),
    )
    monkeypatch.setattr(oas, "_draft_reply", AsyncMock(return_value=draft))
    monkeypatch.setattr(oas, "PROCESSED_EMAIL_IDS", set())

    approvals = []

    class FakeGov:
        def __init__(self, db):
            self.db = db

        def request_approval(self, agent_id, action_type, params, reason):
            approvals.append({"agent_id": agent_id, "action_type": action_type,
                              "params": params, "reason": reason})
            return "hitl-1"

    monkeypatch.setattr(oas, "AgentGovernanceService", FakeGov)
    monkeypatch.setattr(
        oas.manager, "broadcast_event", AsyncMock(return_value=None)
    )
    return session, approvals


@pytest.mark.asyncio
async def test_process_uses_llm_draft_in_hitl_params(monkeypatch):
    session, approvals = _patch_process(
        monkeypatch, emails=[MATCHING_EMAIL], draft="Your custom LLM reply body"
    )
    await oas.process_outlook_automation()

    assert len(approvals) == 1
    params = approvals[0]["params"]
    assert params["to_recipients"] == ["jane@acme.example"]
    assert params["body"] == "Your custom LLM reply body"
    assert params["subject"] == "Re: Quote Request - Press Brake"
    assert params["cc_recipients"] == oas.DEFAULT_CC_RECIPIENTS
    assert session.committed is False or session.closed is True


@pytest.mark.asyncio
async def test_process_falls_back_to_template_when_draft_empty(monkeypatch):
    session, approvals = _patch_process(
        monkeypatch, emails=[MATCHING_EMAIL], draft=""
    )
    await oas.process_outlook_automation()

    assert len(approvals) == 1
    assert approvals[0]["params"]["body"] == oas.DEFAULT_REPLY_TEMPLATE
    assert approvals[0]["params"]["subject"] == "Brennan Machinery"


@pytest.mark.asyncio
async def test_process_uses_template_when_flag_off(monkeypatch):
    session, approvals = _patch_process(
        monkeypatch, emails=[MATCHING_EMAIL], draft="LLM text", flag="false"
    )
    await oas.process_outlook_automation()

    assert len(approvals) == 1
    assert approvals[0]["params"]["body"] == oas.DEFAULT_REPLY_TEMPLATE
    assert oas._draft_reply.await_count == 0


@pytest.mark.asyncio
async def test_process_skips_email_with_existing_hitl(monkeypatch):
    monkeypatch.setenv("ATOM_OUTLOOK_LLM_DRAFTS", "true")
    session = FakeSession()
    monkeypatch.setattr(oas, "SessionLocal", lambda: session)

    # The existing_hitl lookup returns a row -> skip
    hitl = MagicMock()

    class Q:
        def filter(self, *a, **k):
            return self

        def like(self, *a, **k):
            return self

        def first(self):
            return hitl

        def all(self):
            return []

    class S(FakeSession):
        def query(self, *a, **k):
            return Q()

    monkeypatch.setattr(oas, "SessionLocal", lambda: S())
    monkeypatch.setattr(
        oas.outlook_service, "get_unread_emails",
        AsyncMock(return_value=[MATCHING_EMAIL]),
    )
    approvals = []

    class FakeGov:
        def __init__(self, db):
            pass

        def request_approval(self, agent_id, action_type, params, reason):
            approvals.append(params)
            return "hitl-1"

    monkeypatch.setattr(oas, "AgentGovernanceService", FakeGov)
    monkeypatch.setattr(oas, "_draft_reply", AsyncMock(return_value="draft"))
    monkeypatch.setattr(oas, "PROCESSED_EMAIL_IDS", set())

    await oas.process_outlook_automation()

    assert approvals == []
