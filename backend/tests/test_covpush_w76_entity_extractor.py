# -*- coding: utf-8 -*-
"""Coverage wave 76 — core/integration_entity_extractor
(IntegrationEntityExtractor).

No network, no LLM spend: the LLM path is exercised with a stub llm_service
(the real _enhance_with_llm only builds a prompt and never calls out), the
llm-unavailable fallback via a sys.modules blackout, and email validation via
the real email_validator library (check_deliverability=False).

Covers every extraction route (email/crm/communication/project/support/
calendar/generic), per-record exception swallowing, LLM enhance success +
failure, _extract_email_addresses (valid/invalid/validator-ImportError),
_extract_domains (with and without domain), and string-vs-list field
normalization.
"""
import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from core.integration_entity_extractor import IntegrationEntityExtractor


@pytest.fixture()
def extractor():
    return IntegrationEntityExtractor()


class _BoomDict(dict):
    """dict whose .get() raises — exercises except branches."""

    def get(self, *a, **k):
        raise RuntimeError("malformed record")


class _StubLLM:
    """Truthy stand-in; _enhance_with_llm never calls it."""


def _run(awaitable):
    return asyncio.run(awaitable)


# ============================================================================
# Constructor & LLM availability
# ============================================================================

class TestInit:
    def test_llm_service_initialized_when_available(self):
        extractor = IntegrationEntityExtractor()
        assert extractor.llm_service is not None

    def test_llm_service_none_when_import_unavailable(self):
        with patch.dict(sys.modules, {"core.llm_service": None}):
            extractor = IntegrationEntityExtractor()
        assert extractor.llm_service is None


# ============================================================================
# Per-type extraction
# ============================================================================

class TestEmailExtraction:
    def test_email_entity_with_string_fields(self, extractor):
        record = {
            "id": "m1",
            "subject": "Hello <alice@acme.com>",
            "from": "bob@acme.com",
            "to": "alice@acme.com",
            "cc": "carol@beta.io",
            "body": "See you",
            "date": "2026-01-01",
            "url": "https://mail/acme/1",
        }
        entity = extractor._extract_email_entities(record)
        assert entity["id"] == "email_m1"
        assert "Hello" in entity["text"]
        assert set(entity["metadata"]["people"]) == {
            "bob@acme.com", "alice@acme.com", "carol@beta.io"}
        assert set(entity["metadata"]["organizations"]) == {"acme.com", "beta.io"}
        assert entity["metadata"]["date"] == "2026-01-01"

    def test_email_entity_with_list_fields_and_snippet_fallback(self, extractor):
        record = {
            "message_id": "m2",
            "subject": "",
            "from": "boss@acme.com",
            "to": ["a@x.com", "b@x.com"],
            "body": None,
            "snippet": "fallback body",
        }
        entity = extractor._extract_email_entities(record)
        assert entity["id"] == "email_m2"
        assert entity["metadata"]["to"] == ["a@x.com", "b@x.com"]
        assert "fallback body" in entity["text"]

    def test_email_entity_message_id_fallback(self, extractor):
        entity = extractor._extract_email_entities({"message_id": "m3"})
        assert entity["id"] == "email_m3"


class TestCrmExtraction:
    def test_crm_lead(self, extractor):
        record = {"object": "lead", "id": "L1", "name": "Jane Doe",
                  "email": "jane@acme.com", "company": "Acme",
                  "title": "CEO", "phone": "555", "url": "u"}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "lead_L1"
        assert entity["metadata"]["name"] == "Jane Doe"
        assert entity["metadata"]["entity_types"] == ["person", "organization"]

    def test_crm_contact_alternate_keys(self, extractor):
        record = {"type": "contact", "id": "C1", "fullName": "John",
                  "emailAddress": "j@x.com", "companyName": "X",
                  "phoneNumber": "1"}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "contact_C1"
        assert entity["metadata"]["email"] == "j@x.com"

    def test_crm_deal(self, extractor):
        record = {"object": "deal", "id": "D1", "name": "Big Deal",
                  "amount": 1000, "stage": "negotiation",
                  "closeDate": "2026-03-01", "probability": 0.5}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "deal_D1"
        assert entity["metadata"]["amount"] == 1000
        assert "Amount: $1000" in entity["text"]

    def test_crm_opportunity_alternate_keys(self, extractor):
        record = {"type": "opportunity", "id": "O1", "dealName": "Opp",
                  "dealValue": 500, "dealStage": "prospecting"}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "opportunity_O1"
        assert entity["metadata"]["deal_name"] == "Opp"

    def test_crm_account(self, extractor):
        record = {"object": "account", "id": "A1", "name": "Acme Corp",
                  "industry": "Software", "website": "acme.com",
                  "employeeCount": 100, "revenue": 1e6}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "account_A1"
        assert entity["metadata"]["industry"] == "Software"

    def test_crm_company_alternate_keys(self, extractor):
        record = {"type": "company", "id": "A2", "companyName": "Beta"}
        entity = extractor._extract_crm_entities(record)
        assert entity["id"] == "company_A2"

    def test_crm_unknown_type_returns_none(self, extractor):
        assert extractor._extract_crm_entities({"object": "invoice"}) is None


class TestCommunicationExtraction:
    def test_communication_with_mentions_and_urls(self, extractor):
        record = {
            "id": "msg1",
            "text": "Hey @alice please check https://example.com/x and @bob",
            "channel": "general",
            "user": "carol",
            "ts": "123.456",
            "reactions": ["thumbsup"],
            "permalink": "https://slack.com/msg/1",
        }
        entity = extractor._extract_communication_entities(record)
        assert entity["id"] == "message_msg1"
        assert entity["metadata"]["mentions"] == ["alice", "bob"]
        assert entity["metadata"]["urls"] == ["https://example.com/x"]
        assert entity["metadata"]["people"] == ["carol", "alice", "bob"]

    def test_communication_no_user_people_are_mentions(self, extractor):
        record = {"message_id": "m2", "text": "@only", "channelName": "c",
                  "userName": "", "timestamp": "t"}
        entity = extractor._extract_communication_entities(record)
        assert entity["id"] == "message_m2"
        assert entity["metadata"]["people"] == ["only"]


class TestProjectExtraction:
    def test_project_issue(self, extractor):
        record = {"type": "issue", "id": "T1", "summary": "Fix bug",
                  "description": "Details", "status": "open",
                  "assignee": "alice", "priority": "high",
                  "project": "App", "dueDate": "2026-02-01",
                  "self": "https://jira/T1"}
        entity = extractor._extract_project_entities(record)
        assert entity["id"] == "task_T1"
        assert entity["metadata"]["status"] == "open"
        assert entity["metadata"]["url"] == "https://jira/T1"

    def test_project_task_alternate_keys(self, extractor):
        record = {"object": "task", "key": "K-2", "title": "Do thing",
                  "body": "b", "statusName": "done", "assigneeName": "bob",
                  "priorityName": "low", "projectName": "P", "due": "d"}
        entity = extractor._extract_project_entities(record)
        assert entity["id"] == "task_K-2"

    def test_project_project_record(self, extractor):
        record = {"type": "project", "id": "PRJ1", "name": "Launch",
                  "description": "desc", "state": "active",
                  "startDate": "s", "endDate": "e", "url": "u"}
        entity = extractor._extract_project_entities(record)
        assert entity["id"] == "project_PRJ1"
        assert entity["metadata"]["project_name"] == "Launch"

    def test_project_unknown_returns_none(self, extractor):
        assert extractor._extract_project_entities({"type": "board"}) is None


class TestSupportExtraction:
    def test_support_ticket(self, extractor):
        record = {
            "id": "T-9", "subject": "Can't login", "description": "help",
            "status": "open", "priority": "urgent",
            "requester": "bob@x.com", "assignee": "alice",
            "created_at": "c", "updated_at": "u", "url": "https://zd/9",
        }
        entity = extractor._extract_support_entities(record)
        assert entity["id"] == "ticket_T-9"
        assert entity["metadata"]["priority"] == "urgent"
        assert entity["metadata"]["requester"] == "bob@x.com"

    def test_support_ticket_alternate_keys(self, extractor):
        record = {"ticket_id": "T-10", "body": "b",
                  "requester_name": "r", "assignee_name": "a"}
        entity = extractor._extract_support_entities(record)
        assert entity["id"] == "ticket_T-10"
        assert entity["metadata"]["description"] == "b"


class TestCalendarExtraction:
    def test_calendar_event_dict_times(self, extractor):
        record = {
            "id": "E1",
            "summary": "Standup",
            "description": "Daily",
            "start": {"dateTime": "2026-01-01T09:00:00"},
            "end": {"dateTime": "2026-01-01T09:30:00"},
            "attendees": [
                {"email": "a@x.com", "displayName": "Alice"},
                {"name": "Bob"},
                {"displayName": ""},
            ],
            "location": "Room 1",
            "organizer": {"email": "org@x.com"},
            "htmlLink": "https://cal/E1",
        }
        entity = extractor._extract_calendar_entities(record)
        assert entity["id"] == "event_E1"
        assert entity["metadata"]["start_time"] == "2026-01-01T09:00:00"
        assert entity["metadata"]["attendees"] == ["a@x.com", "Bob"]
        assert entity["metadata"]["organizer"] == "org@x.com"
        assert entity["metadata"]["url"] == "https://cal/E1"

    def test_calendar_event_scalar_times_and_date_fallback(self, extractor):
        record = {
            "title": "No Title fallback", "start": "2026-01-01",
            "end": {"date": "2026-01-02"},
            "attendees": "not-a-list",
            "url": "u2",
        }
        entity = extractor._extract_calendar_entities(record)
        assert entity["metadata"]["title"] == "No Title fallback"
        assert entity["metadata"]["start_time"] == "2026-01-01"
        assert entity["metadata"]["end_time"] == "2026-01-02"
        assert entity["metadata"]["attendees"] == []

    def test_calendar_event_scalar_end_time(self, extractor):
        record = {"id": "E2", "summary": "S",
                  "start": {"date": "2026-01-01"}, "end": "2026-01-03"}
        entity = extractor._extract_calendar_entities(record)
        assert entity["metadata"]["start_time"] == "2026-01-01"
        assert entity["metadata"]["end_time"] == "2026-01-03"


class TestGenericExtraction:
    def test_generic_collects_short_strings(self, extractor):
        record = {"id": "G1", "title": "hello", "big": "x" * 2000,
                  "num": 42, "nested": {"a": 1}}
        entity = extractor._extract_generic_entities(record)
        assert entity["id"] == "record_G1"
        assert "hello" in entity["text"]
        assert "x" * 2000 not in entity["text"]
        assert entity["metadata"]["raw_record"] == record


# ============================================================================
# extract() orchestration
# ============================================================================

class TestExtract:
    def test_extract_routes_all_types(self, extractor):
        records = [
            {"type": "email", "id": "1", "subject": "s", "from": "a@x.com",
             "to": [], "body": "b"},
            {"object": "lead", "id": "2", "name": "n"},
            {"id": "3", "text": "@hi"},
            {"type": "task", "id": "4", "summary": "t"},
            {"id": "5", "subject": "sub"},
            {"id": "6", "summary": "cal"},
            {"id": "7", "whatever": "generic"},
        ]
        for integration in ("email", "crm", "communication", "project",
                            "support", "calendar", "unknown"):
            entities = _run(extractor.extract(integration, records))
            assert entities  # every route returns at least one entity

    def test_extract_skips_none_entities(self, extractor):
        entities = _run(extractor.extract("crm", [{"object": "invoice"}]))
        assert entities == []

    def test_extract_swallows_per_record_errors(self, extractor):
        entities = _run(extractor.extract("email", [_BoomDict()]))
        assert entities == []

    def test_extract_with_llm_enhancement(self, extractor):
        extractor.llm_service = _StubLLM()
        record = {"id": "m1", "subject": "s", "from": "a@x.com",
                  "to": [], "body": "b"}
        entities = _run(extractor.extract("email", [record], use_llm=True))
        assert len(entities) == 1
        assert entities[0]["id"] == "email_m1"

    def test_extract_llm_enhancement_exception_swallowed(self, extractor):
        extractor.llm_service = _StubLLM()
        record = {"id": "m1", "subject": "s", "from": "a@x.com",
                  "to": [], "body": "b"}

        def _boom(entity, integration_type):
            raise RuntimeError("llm down")

        with patch.object(extractor, "_enhance_with_llm", new=_boom):
            entities = _run(extractor.extract("email", [record], use_llm=True))
        # the raise escapes into extract()'s per-record handler -> record
        # dropped, extraction continues (does not crash the batch)
        assert entities == []

    def test_enhance_with_llm_no_service_returns_entity(self, extractor):
        extractor.llm_service = None
        entity = {"text": "x"}
        assert _run(extractor._enhance_with_llm(entity, "email")) is entity

    def test_enhance_with_llm_builds_prompt_and_catches_errors(self, extractor):
        extractor.llm_service = _StubLLM()
        entity = {"text": "x"}
        assert _run(extractor._enhance_with_llm(entity, "project")) is entity
        # exception path: a dict whose .get raises
        result = _run(extractor._enhance_with_llm(_BoomDict(), "email"))
        assert isinstance(result, _BoomDict)


# ============================================================================
# Email address & domain helpers
# ============================================================================

class TestEmailHelpers:
    def test_extract_email_addresses_valid_deduplicated(self, extractor):
        data = ["alice@acme.com", "meeting with alice@acme.com",
                "bob+tag@beta.io", 42, None]
        emails = extractor._extract_email_addresses(data)
        assert sorted(emails) == ["alice@acme.com", "bob+tag@beta.io"]

    def test_extract_email_addresses_skips_invalid(self, extractor):
        data = ["not-an-email", "bad@@domain.com", "a@b."]
        assert extractor._extract_email_addresses(data) == []

    def test_extract_email_addresses_regex_match_but_invalid_rfc(self, extractor):
        # "a..b@example.com" matches the regex but fails email-validator RFC
        # validation -> EmailNotValidError branch -> skipped.
        assert extractor._extract_email_addresses(["a..b@example.com"]) == []

    def test_extract_email_addresses_validator_import_fallback(self, extractor):
        with patch.dict(sys.modules, {"email_validator": None}):
            emails = extractor._extract_email_addresses(
                ["alice@acme.com", "definitely-not-an-email"])
        assert "alice@acme.com" in emails
        assert len(emails) == 1

    def test_extract_domains_deduplicated(self, extractor):
        emails = ["a@acme.com", "b@acme.com", "c@beta.io"]
        assert sorted(extractor._extract_domains(emails)) == \
            ["acme.com", "beta.io"]

    def test_extract_domains_ignores_maformed(self, extractor):
        assert extractor._extract_domains(["no-domain-here"]) == []

    def test_extract_domains_skips_missing_at(self, extractor):
        with patch.object(extractor, "_extract_email_addresses",
                          return_value=["missing-domain"]):
            assert extractor._extract_domains(["missing-domain"]) == []

    def test_extract_domains_empty_input(self, extractor):
        assert extractor._extract_domains([]) == []
