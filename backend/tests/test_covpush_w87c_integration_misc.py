# -*- coding: utf-8 -*-
"""Coverage wave 87c — 10 core/* integration/lifecycle modules.

Standalone re-derivation of >=95% statement coverage for:

  core/integration_entity_extractor.py
  core/integration_http.py
  core/integration_loader.py
  core/intervention_service.py
  core/knowledge_query_endpoints.py
  core/lifecycle_comm_generator.py
  core/marketplace_usage_tracker.py
  core/memory_integration_mixin.py
  core/meta_automation.py
  core/model_factory.py

Style: mocked deps, zero LLM spend, no network (httpx client is a fake),
no real DB (get_db_session / models are mocked; no SQLite needed).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import types
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.integration_entity_extractor import IntegrationEntityExtractor
from core.integration_http import IntegrationHTTP, get_integration_http
from core.integration_loader import IntegrationLoader, auto_ingest
from core.intervention_service import InterventionService
from core.knowledge_query_endpoints import (
    KnowledgeQueryManager,
    KnowledgeQueryRequest,
    get_knowledge_query_manager,
    knowledge_query,
)
from core.lifecycle_comm_generator import LifecycleCommGenerator
from core.marketplace_usage_tracker import MarketplaceUsageTracker
from core.memory_integration_mixin import (
    BackfillJob,
    IntegrationBackfillManager,
    MemoryIntegrationMixin,
    _backfill_jobs,
)
from core.meta_automation import MetaAutomationEngine, get_meta_automation
from core.model_factory import ModelFactory, get_model_factory


# ============================================================================
# 1. core/integration_entity_extractor.py
# ============================================================================


@pytest.fixture
def extractor():
    with patch("core.llm_service.LLMService", new=MagicMock()):
        ex = IntegrationEntityExtractor()
    ex.llm_service = None
    return ex


class TestIntegrationEntityExtractorInit:
    def test_llm_service_initialized_when_available(self):
        with patch("core.llm_service.LLMService", new=MagicMock()) as cls:
            ex = IntegrationEntityExtractor()
            assert ex.llm_service is cls.return_value

    def test_llm_service_none_when_import_unavailable(self):
        with patch.dict(sys.modules, {"core.llm_service": None}):
            ex = IntegrationEntityExtractor()
            assert ex.llm_service is None

    def test_regex_patterns_compiled(self, extractor):
        assert extractor.email_pattern.match("a@b.com")
        assert extractor.username_pattern.findall("hi @joe") == ["joe"]
        assert extractor.date_pattern.match("2026-01-15")
        assert extractor.url_pattern.match("https://example.com")


class TestEntityEmail:
    def test_email_with_list_fields(self, extractor):
        e = extractor._extract_email_entities({
            "id": "e1", "subject": "Hello", "from": "a@x.com",
            "to": ["b@x.com", "c@y.com"], "cc": ["d@z.com"], "body": "Body text",
            "date": "2026-01-01", "url": "http://u",
        })
        assert e["id"] == "email_e1"
        assert sorted(e["metadata"]["people"]) == sorted(["a@x.com", "b@x.com", "c@y.com", "d@z.com"])
        assert sorted(e["metadata"]["organizations"]) == ["x.com", "y.com", "z.com"]
        assert e["metadata"]["entity_types"] == ["person", "organization", "email_thread"]

    def test_email_with_string_fields_and_snippet_fallback(self, extractor):
        e = extractor._extract_email_entities({
            "message_id": "m1", "subject": "S", "from": "a@x.com",
            "to": "b@y.com", "cc": "c@z.com", "snippet": "snippet text",
        })
        assert e["id"] == "email_m1"
        assert e["metadata"]["to"] == ["b@y.com"]
        assert e["metadata"]["cc"] == ["c@z.com"]
        assert "snippet text" in e["text"]

    def test_email_without_body_or_snippet(self, extractor):
        e = extractor._extract_email_entities({"id": "e2", "subject": "S", "from": ""})
        assert e["metadata"]["from"] == ""
        assert e["text"] == "S\n"


class TestEntityCrm:
    def test_crm_lead(self, extractor):
        e = extractor._extract_crm_entities({
            "object": "lead", "id": "L1", "name": "Jane", "email": "j@c.com",
            "company": "ACME", "title": "CEO", "phone": "555", "url": "u",
        })
        assert e["id"] == "lead_L1"
        assert e["metadata"]["record_type"] == "lead"
        assert "Jane" in e["text"]

    def test_crm_contact_alternate_keys(self, extractor):
        e = extractor._extract_crm_entities({
            "type": "contact", "id": "C1", "fullName": "Bob",
            "emailAddress": "b@c.com", "companyName": "Corp", "phoneNumber": "1",
        })
        assert e["id"] == "contact_C1"
        assert e["metadata"]["name"] == "Bob"
        assert e["metadata"]["company"] == "Corp"

    def test_crm_deal(self, extractor):
        e = extractor._extract_crm_entities({
            "object": "deal", "id": "D1", "name": "Big Deal",
            "amount": 1000, "stage": "Negotiation", "closeDate": "2026-02-01",
            "probability": 0.5, "url": "u",
        })
        assert e["id"] == "deal_D1"
        assert e["metadata"]["entity_types"] == ["deal", "organization"]
        assert "$1000" in e["text"]

    def test_crm_opportunity_alternate_keys(self, extractor):
        e = extractor._extract_crm_entities({
            "type": "opportunity", "id": "O1", "dealName": "Opp",
            "dealValue": 50, "dealStage": "Closed",
        })
        assert e["id"] == "opportunity_O1"
        assert e["metadata"]["amount"] == 50

    def test_crm_account(self, extractor):
        e = extractor._extract_crm_entities({
            "object": "account", "id": "A1", "name": "ACME Inc",
            "industry": "Tech", "website": "acme.com", "employeeCount": 10,
            "revenue": 999, "url": "u",
        })
        assert e["id"] == "account_A1"
        assert e["metadata"]["entity_types"] == ["organization"]

    def test_crm_company_alternate_keys(self, extractor):
        e = extractor._extract_crm_entities({
            "type": "company", "id": "CO1", "companyName": "Other Inc",
        })
        assert e["id"] == "company_CO1"

    def test_crm_unknown_type_returns_none(self, extractor):
        assert extractor._extract_crm_entities({"object": "weird"}) is None


class TestEntityCommunication:
    def test_communication_with_mentions_and_urls(self, extractor):
        e = extractor._extract_communication_entities({
            "id": "m1", "text": "hi @alice check https://x.com",
            "channel": "general", "user": "bob", "ts": 123,
            "reactions": ["thumbsup"], "permalink": "p",
        })
        assert e["id"] == "message_m1"
        assert e["metadata"]["mentions"] == ["alice"]
        assert e["metadata"]["urls"] == ["https://x.com"]
        assert e["metadata"]["people"] == ["bob", "alice"]

    def test_communication_no_user_people_are_mentions(self, extractor):
        e = extractor._extract_communication_entities({
            "message_id": "m2", "text": "ping @sam", "channelName": "ch", "userName": "u",
            "timestamp": "t",
        })
        assert e["id"] == "message_m2"
        assert e["metadata"]["people"] == ["u", "sam"]


class TestEntityProject:
    def test_project_issue(self, extractor):
        e = extractor._extract_project_entities({
            "type": "issue", "id": "I1", "summary": "Bug", "description": "desc",
            "status": "Open", "assignee": "Al", "priority": "High",
            "project": "Proj", "dueDate": "d", "url": "u",
        })
        assert e["id"] == "task_I1"
        assert e["metadata"]["record_type"] == "task"

    def test_project_task_alternate_keys(self, extractor):
        e = extractor._extract_project_entities({
            "object": "task", "key": "K1", "title": "T", "body": "b",
            "statusName": "Done", "assigneeName": "Ax", "priorityName": "P",
            "projectName": "Pr", "due": "d", "self": "s",
        })
        assert e["id"] == "task_K1"
        assert e["metadata"]["title"] == "T"

    def test_project_project_record(self, extractor):
        e = extractor._extract_project_entities({
            "type": "project", "id": "P1", "name": "Alpha", "description": "d",
            "state": "Active", "startDate": "s", "endDate": "e", "url": "u",
        })
        assert e["id"] == "project_P1"
        assert e["metadata"]["record_type"] == "project"

    def test_project_unknown_returns_none(self, extractor):
        assert extractor._extract_project_entities({"type": "milestone"}) is None


class TestEntitySupport:
    def test_support_ticket(self, extractor):
        e = extractor._extract_support_entities({
            "id": "T1", "subject": "subj", "description": "desc", "status": "open",
            "priority": "high", "requester": "rq", "assignee": "as",
            "created_at": "c", "updated_at": "u", "url": "url",
        })
        assert e["id"] == "ticket_T1"
        assert e["metadata"]["ticket_id"] == "T1"

    def test_support_ticket_alternate_keys(self, extractor):
        e = extractor._extract_support_entities({
            "ticket_id": "T2", "body": "b", "requester_name": "r", "assignee_name": "a",
        })
        assert e["id"] == "ticket_T2"
        assert e["metadata"]["requester"] == "r"


class TestEntityCalendar:
    def test_calendar_dict_times_and_attendees(self, extractor):
        e = extractor._extract_calendar_entities({
            "id": "EV1", "summary": "Meet", "description": "d",
            "start": {"dateTime": "2026-01-01T10:00"}, "end": {"date": "2026-01-01T11:00"},
            "attendees": [
                {"email": "a@x.com", "displayName": "A"},
                {"name": "NoEmail"},
                {"email": ""},
            ],
            "location": "loc", "organizer": {"email": "o@x.com"}, "htmlLink": "h",
        })
        assert e["id"] == "event_EV1"
        assert e["metadata"]["start_time"] == "2026-01-01T10:00"
        assert e["metadata"]["end_time"] == "2026-01-01T11:00"
        assert e["metadata"]["attendees"] == ["a@x.com", "NoEmail"]

    def test_calendar_scalar_times_and_title_fallback(self, extractor):
        e = extractor._extract_calendar_entities({
            "id": "EV2", "title": "T2", "start": "2026-01-01", "end": "2026-01-02",
        })
        assert e["metadata"]["start_time"] == "2026-01-01"
        assert e["metadata"]["end_time"] == "2026-01-02"
        assert e["metadata"]["title"] == "T2"

    def test_calendar_default_title_no_attendees(self, extractor):
        e = extractor._extract_calendar_entities({"id": "EV3"})
        assert e["metadata"]["title"] == "No Title"
        assert e["metadata"]["attendees"] == []


class TestEntityGeneric:
    def test_generic_collects_short_strings(self, extractor):
        e = extractor._extract_generic_entities({
            "id": "R1", "name": "abc", "big": "x" * 2000, "num": 5,
        })
        assert e["id"] == "record_R1"
        assert e["metadata"]["raw_record"]["name"] == "abc"
        assert "abc" in e["text"]
        assert "x" * 2000 not in e["text"]

    def test_generic_empty_record(self, extractor):
        e = extractor._extract_generic_entities({"id": "R2"})
        assert e["text"] == "R2"


class TestExtract:
    def test_extract_routes_all_types(self, extractor):
        records = [
            {"id": "1", "subject": "s", "from": "a@x.com", "body": "hello"},
            {"id": "2", "object": "lead", "name": "n"},
            {"id": "3", "text": "hi"},
            {"id": "4", "type": "task", "summary": "t"},
            {"id": "5", "subject": "sup"},
            {"id": "6", "summary": "cal", "start": "2026-01-01"},
            {"id": "7", "foo": "bar"},
        ]
        entities = asyncio.run(extractor.extract("unknown", records))
        assert len(entities) == 7
        assert entities[6]["metadata"]["integration"] == "other"

    async def test_extract_per_type(self, extractor):
        expected = ["email", "crm", "communication", "project", "support", "calendar"]
        for itype, exp in zip([
            ("email", {"id": "1", "subject": "s", "from": "a@x.com", "body": "b"}),
            ("crm", {"object": "lead", "name": "n"}),
            ("communication", {"text": "t"}),
            ("project", {"type": "task", "summary": "t"}),
            ("support", {"id": "t1"}),
            ("calendar", {"summary": "c"}),
        ], expected):
            entities = await extractor.extract(itype[0], [itype[1]])
            assert entities[0]["metadata"]["integration"] == exp

    def test_extract_skips_none_entities(self, extractor):
        with patch.object(extractor, "_extract_crm_entities", return_value=None):
            entities = asyncio.run(extractor.extract("crm", [{"object": "x"}]))
        assert entities == []

    def test_extract_swallows_per_record_errors(self, extractor):
        with patch.object(extractor, "_extract_email_entities", side_effect=RuntimeError("boom")):
            entities = asyncio.run(extractor.extract("email", [{"id": "1"}]))
        assert entities == []

    def test_extract_with_llm_enhancement(self, extractor):
        extractor.llm_service = MagicMock()
        entities = asyncio.run(extractor.extract("email", [{"id": "1", "subject": "s", "from": "a@x.com", "body": "b"}], use_llm=True))
        assert len(entities) == 1
        assert extractor.llm_service is not None

    def test_extract_llm_enhancement_exception_swallowed(self, extractor):
        async def _boom(entity, itype):
            raise RuntimeError("llm fail")
        with patch.object(extractor, "_enhance_with_llm", new=_boom):
            entities = asyncio.run(extractor.extract("crm", [{"object": "lead", "name": "n"}], use_llm=True))
        assert len(entities) == 1

    def test_extract_no_llm_enhancement_when_service_none(self, extractor):
        entities = asyncio.run(extractor.extract("crm", [{"object": "lead", "name": "n"}], use_llm=True))
        assert entities[0]["metadata"]["name"] == "n"


class TestEnhanceWithLlm:
    def test_no_service_returns_entity_unchanged(self, extractor):
        entity = {"id": "1", "text": "t"}
        assert asyncio.run(extractor._enhance_with_llm(entity, "email")) is entity

    def test_builds_prompt_and_returns_entity(self, extractor):
        extractor.llm_service = MagicMock()
        entity = {"id": "1", "text": "hello"}
        out = asyncio.run(extractor._enhance_with_llm(entity, "email"))
        assert out["id"] == "1"

    def test_default_prompt_for_unknown_type(self, extractor):
        extractor.llm_service = MagicMock()
        entity = {"id": "1", "text": "hello"}
        out = asyncio.run(extractor._enhance_with_llm(entity, "other"))
        assert out is entity

    def test_exception_caught(self, extractor):
        extractor.llm_service = MagicMock()
        with patch.object(extractor.llm_service, "complete", side_effect=RuntimeError("x")):
            entity = {"id": "1", "text": "hello"}
            out = asyncio.run(extractor._enhance_with_llm(entity, "email"))
        assert out is entity

    def test_prompt_build_error_caught(self, extractor):
        extractor.llm_service = MagicMock()
        entity = MagicMock()
        entity.get.side_effect = RuntimeError("prompt build failed")
        out = asyncio.run(extractor._enhance_with_llm(entity, "email"))
        assert out is entity


class TestEmailAddresses:
    def test_valid_deduplicated(self, extractor):
        out = extractor._extract_email_addresses(["a@x.com", "b@y.com", "a@x.com", 42])
        assert sorted(out) == ["a@x.com", "b@y.com"]

    def test_validator_rejects_invalid(self, extractor):
        import email_validator
        with patch("email_validator.validate_email", side_effect=email_validator.EmailNotValidError("bad")):
            out = extractor._extract_email_addresses(["bad@example.com"])
        assert out == []

    def test_validator_import_fallback_regex_only(self, extractor):
        with patch.dict(sys.modules, {"email_validator": None}):
            out = extractor._extract_email_addresses(["a@x.com"])
        assert out == ["a@x.com"]

    def test_email_pattern_skips_non_string(self, extractor):
        assert extractor._extract_email_addresses([None, 5, "nope-no-at"]) == []


class TestDomains:
    def test_domains_deduplicated(self, extractor):
        out = extractor._extract_domains(["a@x.com", "b@x.com", "c@y.com"])
        assert sorted(out) == ["x.com", "y.com"]

    def test_domains_skips_malformed(self, extractor):
        with patch.object(extractor, "_extract_email_addresses", return_value=["no-at-sign"]):
            assert extractor._extract_domains([]) == []

    def test_domains_no_emails(self, extractor):
        with patch.object(extractor, "_extract_email_addresses", return_value=[]):
            assert extractor._extract_domains([]) == []


# ============================================================================
# 2. core/integration_http.py
# ============================================================================


class _FakeClient:
    """Deterministic httpx.AsyncClient stand-in (no network)."""

    def __init__(self, responses=None, side_effect=None):
        self.responses = list(responses or [])
        self.side_effect = side_effect
        self.calls = []
        self.aclosed = False

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.side_effect is not None:
            raise self.side_effect
        if self.responses:
            return self.responses.pop(0)
        return httpx.Response(200)

    async def aclose(self):
        self.aclosed = True


def _resp(status, **kwargs):
    return httpx.Response(status, **kwargs)


def _patch_resilience(cb=None, rl=None, health=None, backoff=0.0, is_enabled=None,
                      is_enabled_side_effect=None, rl_limited=(False, 0), rl_side_effect=None,
                      cb_record_success_side_effect=None, cb_record_failure_side_effect=None):
    """Patch circuit breaker / rate limiter / health monitor imports.

    Returns an ExitStack ready for `with`.
    """
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch("core.integration_http.asyncio.sleep", new=AsyncMock()))
    if cb is not None:
        if is_enabled is None and is_enabled_side_effect is None:
            is_enabled = True
        cb.is_enabled = AsyncMock(return_value=is_enabled, side_effect=is_enabled_side_effect)
        cb.record_success = AsyncMock(side_effect=cb_record_success_side_effect)
        cb.record_failure = AsyncMock(side_effect=cb_record_failure_side_effect)
        stack.enter_context(patch("core.circuit_breaker.circuit_breaker", cb))
    if rl is not None:
        rl.is_rate_limited = AsyncMock(return_value=rl_limited, side_effect=rl_side_effect)
        stack.enter_context(patch("core.rate_limiter.rate_limiter", rl))
        stack.enter_context(patch("core.rate_limiter.calculate_backoff", return_value=backoff))
    if health is not None:
        stack.enter_context(patch("core.integration_health_monitor.get_integration_health_monitor", return_value=health))
    return stack


class TestIntegrationHttpBasics:
    def test_constructor_owns_default_client(self):
        http = IntegrationHTTP()
        assert http._owns_client is True
        assert isinstance(http._client, httpx.AsyncClient)

    def test_constructor_uses_provided_client(self):
        client = _FakeClient()
        http = IntegrationHTTP(client=client)
        assert http._owns_client is False
        assert http._client is client

    def test_close_owned_client(self):
        with patch("core.integration_http.httpx.AsyncClient") as cls:
            cls.return_value.aclose = AsyncMock()
            http = IntegrationHTTP()
            asyncio.run(http.close())
            cls.return_value.aclose.assert_awaited_once()

    def test_close_does_not_close_unowned_client(self):
        client = _FakeClient()
        http = IntegrationHTTP(client=client)
        asyncio.run(http.close())
        assert client.aclosed is False

    def test_get_integration_http_singleton(self):
        with patch("core.integration_http._integration_http", None):
            a = get_integration_http()
            b = get_integration_http()
            assert a is b
            assert isinstance(a, IntegrationHTTP)

    def test_convenience_methods(self):
        http = IntegrationHTTP(client=_FakeClient())
        for method, name in [("GET", "get"), ("POST", "post"), ("PUT", "put"),
                             ("PATCH", "patch"), ("DELETE", "delete")]:
            with patch.object(IntegrationHTTP, "request", new=AsyncMock(return_value=_resp(200))) as req:
                fn = getattr(http, name)
                resp = asyncio.run(fn("slack", "http://x"))
                assert resp.status_code == 200
                req.assert_awaited_once_with("slack", method, "http://x")


class TestIntegrationHttpSuccess:
    def test_success_records_circuit_and_health(self):
        cb = MagicMock()
        health = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, rl=MagicMock(), health=health):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200
        cb.record_success.assert_awaited_once_with("slack")
        health.record.assert_called_once()
        args = health.record.call_args
        assert args.kwargs["success"] is True

    def test_success_without_cb_or_health(self):
        with patch.dict(sys.modules, {
            "core.circuit_breaker": None,
            "core.rate_limiter": None,
            "core.integration_health_monitor": None,
        }):
            client = _FakeClient(responses=[_resp(200)])
            http = IntegrationHTTP(client=client)
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200

    def test_success_passes_kwargs_and_timeout(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        to = httpx.Timeout(1.0)
        with _patch_resilience(cb=cb):
            asyncio.run(http.request("slack", "POST", "http://x",
                                     headers={"h": "1"}, params={"p": "2"},
                                     json={"j": 1}, data=b"d", timeout=to,
                                     extensions={"e": 1}))
        method, url, kwargs = client.calls[0]
        assert kwargs["headers"] == {"h": "1"}
        assert kwargs["params"] == {"p": "2"}
        assert kwargs["json"] == {"j": 1}
        assert kwargs["data"] == b"d"
        assert kwargs["timeout"] is to
        assert kwargs["extensions"] == {"e": 1}

    def test_success_record_failure_sideeffect_safe(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, cb_record_success_side_effect=RuntimeError("cb down")):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200


class TestIntegrationHttpCircuitBreaker:
    def test_circuit_open_raises_http_status_error(self):
        cb = MagicMock()
        http = IntegrationHTTP(client=_FakeClient(responses=[_resp(200)]))
        with _patch_resilience(cb=cb, is_enabled=False), pytest.raises(httpx.HTTPStatusError) as ei:
            asyncio.run(http.request("slack", "GET", "http://x"))
        assert "Circuit breaker open" in str(ei.value)
        assert ei.value.response.status_code == 503

    def test_circuit_check_httpx_error_reraised(self):
        cb = MagicMock()
        err = httpx.HTTPStatusError("x", request=httpx.Request("GET", "u"), response=_resp(503))
        http = IntegrationHTTP(client=_FakeClient(responses=[_resp(200)]))
        with _patch_resilience(cb=cb, is_enabled_side_effect=err), pytest.raises(httpx.HTTPStatusError):
            asyncio.run(http.request("slack", "GET", "http://x"))

    def test_circuit_check_generic_error_proceeds(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, is_enabled_side_effect=RuntimeError("db down")):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200


class TestIntegrationHttpRateLimiter:
    def test_rate_limited_waits(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, rl=MagicMock(), rl_limited=(True, 3.5)):
            asyncio.run(http.request("slack", "GET", "http://x"))

    def test_rate_limited_zero_remaining_no_wait(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, rl=MagicMock(), rl_limited=(True, 0)):
            asyncio.run(http.request("slack", "GET", "http://x"))

    def test_rate_limiter_error_proceeds(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, rl=MagicMock(), rl_side_effect=RuntimeError("rl down")):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200


class TestIntegrationHttpRetries:
    def test_429_retry_then_success(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(429), _resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200
        assert len(client.calls) == 2

    def test_429_with_retry_after_header(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(429, headers={"Retry-After": "1"}), _resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200

    def test_429_on_final_attempt_returns_response(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(429)] * 4)
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 429
        cb.record_failure.assert_awaited_once_with("slack")

    def test_500_retry_then_success(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(500), _resp(503), _resp(200)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 200
        assert len(client.calls) == 3

    def test_500_on_final_attempt_returns_response(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(500)] * 4)
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 500

    def test_401_refresh_then_success(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(401), _resp(200)])
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(return_value={"Authorization": "Bearer new"})
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x", token_refresh_fn=refresh))
        assert resp.status_code == 200
        refresh.assert_awaited_once()
        assert client.calls[1][2]["headers"]["Authorization"] == "Bearer new"

    def test_401_refresh_returns_none_falls_through(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(401)])
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(return_value=None)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x", token_refresh_fn=refresh))
        assert resp.status_code == 401
        cb.record_failure.assert_awaited_once()

    def test_401_refresh_raises(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(401)])
        http = IntegrationHTTP(client=client)
        refresh = AsyncMock(side_effect=RuntimeError("refresh failed"))
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x", token_refresh_fn=refresh))
        assert resp.status_code == 401

    def test_401_without_refresh_fn(self):
        cb = MagicMock()
        client = _FakeClient(responses=[_resp(401)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 401

    def test_404_non_retryable_records_failure(self):
        cb = MagicMock()
        health = MagicMock()
        client = _FakeClient(responses=[_resp(404)])
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, rl=MagicMock(), health=health,
                               cb_record_failure_side_effect=RuntimeError("cb down")):
            resp = asyncio.run(http.request("slack", "GET", "http://x"))
        assert resp.status_code == 404
        assert len(client.calls) == 1
        cb.record_failure.assert_awaited_once_with("slack")
        health.record.assert_called_once()


class TestIntegrationHttpNetworkErrors:
    def test_request_error_retries_then_raises(self):
        cb = MagicMock()
        err = httpx.ConnectError("net down", request=httpx.Request("GET", "http://x"))
        client = _FakeClient(side_effect=err)
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=cb, cb_record_failure_side_effect=RuntimeError("cb down")):
            with pytest.raises(httpx.RequestError):
                asyncio.run(http.request("slack", "GET", "http://x"))
        assert len(client.calls) == 4
        assert cb.record_failure.await_count == 4

    def test_request_error_records_health_failure(self):
        health = MagicMock()
        err = httpx.ConnectError("net down", request=httpx.Request("GET", "http://x"))
        client = _FakeClient(side_effect=err)
        http = IntegrationHTTP(client=client)
        with _patch_resilience(cb=MagicMock(), rl=MagicMock(), health=health):
            with pytest.raises(httpx.RequestError):
                asyncio.run(http.request("slack", "GET", "http://x"))
        assert health.record.call_count == 4


class TestParseRetryAfter:
    def test_missing_header_default(self):
        http = IntegrationHTTP(client=_FakeClient())
        assert http._parse_retry_after(_resp(429), "slack") == 2.0

    def test_integer_seconds(self):
        http = IntegrationHTTP(client=_FakeClient())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": "7"}), "slack") == 7.0

    def test_float_seconds(self):
        http = IntegrationHTTP(client=_FakeClient())
        assert http._parse_retry_after(_resp(429, headers={"retry-after": "1.5"}), "slack") == 1.5

    def test_http_date_future_clamped(self):
        http = IntegrationHTTP(client=_FakeClient())
        from email.utils import format_datetime
        from datetime import timedelta
        future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=60))
        value = http._parse_retry_after(_resp(429, headers={"Retry-After": future}), "slack")
        assert value >= 1.0 and value <= 300.0

    def test_http_date_past_min_one(self):
        http = IntegrationHTTP(client=_FakeClient())
        from email.utils import format_datetime
        past = format_datetime(datetime.now(timezone.utc))
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": past}), "slack") == 1.0

    def test_invalid_date_default(self):
        http = IntegrationHTTP(client=_FakeClient())
        assert http._parse_retry_after(_resp(429, headers={"Retry-After": "not-a-date"}), "slack") == 2.0


# ============================================================================
# 3. core/integration_loader.py
# ============================================================================


class TestValidateModulePath:
    def test_valid_path(self):
        assert IntegrationLoader()._validate_module_path("integrations.asana_routes") is True

    def test_invalid_path_traversal(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("../evil")

    def test_invalid_path_uppercase(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("Integrations.Foo")

    def test_blocked_prefix_os(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("os.system")

    def test_blocked_prefix_sys(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("sys.exit")

    def test_blocked_prefix_subprocess(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("subprocess.run")

    def test_blocked_prefix_eval(self):
        with pytest.raises(ValueError):
            IntegrationLoader()._validate_module_path("evaluate.thing")


class TestLoadIntegration:
    def test_condition_false_returns_none(self):
        assert IntegrationLoader().load_integration("foo.bar", condition=False) is None

    def test_successful_load(self):
        router = object()
        module = SimpleNamespace(router=router)
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            loader = IntegrationLoader()
            result = loader.load_integration("integrations.test_mod")
        assert result is router
        assert loader.integrations == [{"name": "integrations.test_mod", "router": router, "status": "loaded"}]
        assert loader.get_loaded_integrations() == [{"name": "integrations.test_mod", "router": router, "status": "loaded"}]

    def test_timeout_marks_failed(self):
        def slow(module_path, router_name):
            time.sleep(0.2)
            return object()
        with patch.object(IntegrationLoader, "_load_module_with_timeout", side_effect=slow):
            loader = IntegrationLoader(timeout=0.01)
            result = loader.load_integration("slow.mod")
        assert result is None
        assert loader.integrations[0]["status"] == "timeout"
        assert "Timeout" in loader.integrations[0]["error"]

    def test_import_error_marks_failed(self):
        with patch("core.integration_loader.importlib.import_module", side_effect=ImportError("no module")):
            loader = IntegrationLoader()
            result = loader.load_integration("missing.mod")
        assert result is None
        assert loader.integrations[0]["status"] == "failed"
        assert "no module" in loader.integrations[0]["error"]

    def test_attribute_error_returns_none(self):
        module = SimpleNamespace()
        with patch("core.integration_loader.importlib.import_module", return_value=module):
            loader = IntegrationLoader()
            result = loader.load_integration("integrations.test_mod", router_name="missing_router")
        assert result is None
        assert loader.integrations == []

    def test_generic_error_marks_error(self):
        with patch("core.integration_loader.importlib.import_module", side_effect=RuntimeError("boom")):
            loader = IntegrationLoader()
            result = loader.load_integration("broken.mod")
        assert result is None
        assert loader.integrations[0]["status"] == "error"

    def test_invalid_path_raises_value_error_status(self):
        loader = IntegrationLoader()
        result = loader.load_integration("../evil")
        assert result is None
        assert loader.integrations[0]["status"] == "error"
        assert "Invalid module path" in loader.integrations[0]["error"]

    def test_get_loaded_integrations_filters(self):
        loader = IntegrationLoader()
        router = object()
        loader.integrations = [
            {"name": "a", "router": router, "status": "loaded"},
            {"name": "b", "router": None, "status": "failed"},
            {"name": "c", "router": None, "status": "timeout"},
        ]
        assert len(loader.get_loaded_integrations()) == 1


class TestAutoIngest:
    def _patch_pipeline(self):
        pipeline = MagicMock()
        patchers = [patch("core.integration_loader.atom_ingestion_pipeline", pipeline)]
        for p in patchers:
            p.start()
        return pipeline

    def test_async_list(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        async def fn():
            return [{"a": 1}, {"b": 2}]

        result = asyncio.run(fn())
        assert result == [{"a": 1}, {"b": 2}]
        assert pipeline.ingest_record.call_count == 2
        pipeline.ingest_record.assert_any_call("app", "rec", {"a": 1})

    def test_async_dict(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        async def fn():
            return {"a": 1}

        assert asyncio.run(fn()) == {"a": 1}
        pipeline.ingest_record.assert_called_once_with("app", "rec", {"a": 1})

    def test_async_empty(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        async def fn():
            return []

        assert asyncio.run(fn()) == []
        pipeline.ingest_record.assert_not_called()

    def test_async_none(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        async def fn():
            return None

        assert asyncio.run(fn()) is None
        pipeline.ingest_record.assert_not_called()

    def test_sync_list(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        def fn():
            return [{"a": 1}]

        assert fn() == [{"a": 1}]
        pipeline.ingest_record.assert_called_once_with("app", "rec", {"a": 1})

    def test_sync_dict(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        def fn():
            return {"x": 2}

        assert fn() == {"x": 2}
        pipeline.ingest_record.assert_called_once_with("app", "rec", {"x": 2})

    def test_sync_none(self):
        pipeline = self._patch_pipeline()

        @auto_ingest("app", "rec")
        def fn():
            return None

        assert fn() is None

    def test_async_ingest_error_swallowed(self):
        pipeline = self._patch_pipeline()
        pipeline.ingest_record.side_effect = RuntimeError("ingest down")

        @auto_ingest("app", "rec")
        async def fn():
            return [{"a": 1}]

        assert asyncio.run(fn()) == [{"a": 1}]

    def test_sync_ingest_error_swallowed(self):
        pipeline = self._patch_pipeline()
        pipeline.ingest_record.side_effect = RuntimeError("ingest down")

        @auto_ingest("app", "rec")
        def fn():
            return {"a": 1}

        assert fn() == {"a": 1}


# ============================================================================
# 4. core/intervention_service.py
# ============================================================================


class TestInterventionService:
    def _db_fixture(self, cm_side_effect=None):
        """Patch get_db_session; returns the fake db object."""
        get_db = MagicMock()
        if cm_side_effect is not None:
            get_db.return_value.__enter__.side_effect = cm_side_effect
        p = patch("core.intervention_service.get_db_session", get_db)
        p.start()
        self._patchers = [p]
        return get_db.return_value.__enter__.return_value

    def _fake_action(self, **kw):
        base = {
            "id": "hitl-1", "agent_id": "ag-1", "user_id": "u-1",
            "action_type": "read", "platform": "slack", "params": {"k": "v"},
            "reason": "need approval", "created_at": SimpleNamespace(
                isoformat=lambda: "2026-01-01T00:00:00"),
            "status": "pending",
        }
        base.update(kw)
        return SimpleNamespace(**base)

    def test_singleton_exists(self):
        from core.intervention_service import intervention_service
        assert isinstance(intervention_service, InterventionService)

    def test_request_intervention_success(self):
        db = self._db_fixture()
        with patch("core.intervention_service.HITLAction", new=MagicMock()) as model:
            model.return_value.id = "hitl-42"
            svc = InterventionService()
            result = asyncio.run(svc.request_intervention(
                "ws-1", "approve_spend", "slack", {"amt": 5}, "reason here",
                agent_id="ag-1", user_id="u-1"))
        assert result["status"] == "PAUSED"
        assert result["action_id"] == "hitl-42"
        assert result["requires_approval"] is True
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once_with(model.return_value)

    def test_request_intervention_no_agent(self):
        db = self._db_fixture()
        with patch("core.intervention_service.HITLAction", new=MagicMock()) as model:
            model.return_value.id = "hitl-1"
            result = asyncio.run(InterventionService().request_intervention(
                "ws-1", "read", "gmail", {}, "why"))
        assert result["status"] == "PAUSED"

    def test_request_intervention_exception_returns_error(self):
        self._db_fixture(cm_side_effect=RuntimeError("db down"))
        result = asyncio.run(InterventionService().request_intervention(
            "ws-1", "read", "gmail", {}, "why"))
        assert result["status"] == "ERROR"
        assert "Failed to persist intervention request" in result["message"]

    def test_get_pending_default_workspace(self):
        db = self._db_fixture()
        action = self._fake_action()
        db.query.return_value.filter.return_value.all.return_value = [action]
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.intervention_service.HITLAction", new=MagicMock()), \
             patch("core.intervention_service.AgentRegistry", new=MagicMock()):
            results = InterventionService().get_pending_interventions()
        assert results[0]["id"] == "hitl-1"
        assert results[0]["agent_name"] == "Unknown Agent"
        assert results[0]["created_at"] == "2026-01-01T00:00:00"

    def test_get_pending_workspace_filter_applied(self):
        db = self._db_fixture()
        action = self._fake_action(agent_id=None)
        db.query.return_value.filter.return_value.filter.return_value.all.return_value = [action]
        db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
        with patch("core.intervention_service.HITLAction", new=MagicMock()), \
             patch("core.intervention_service.AgentRegistry", new=MagicMock()):
            results = InterventionService().get_pending_interventions(workspace_id="ws-9")
        assert results[0]["agent_name"] == "Unknown Agent"
        assert results[0]["user_id"] == "u-1"

    def test_get_pending_resolves_agent_name(self):
        db = self._db_fixture()
        action = self._fake_action()
        db.query.return_value.filter.return_value.all.return_value = [action]
        db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(name="Sales Bot")
        with patch("core.intervention_service.HITLAction", new=MagicMock()), \
             patch("core.intervention_service.AgentRegistry", new=MagicMock()):
            results = InterventionService().get_pending_interventions(workspace_id="default", user_id="u-1")
        assert results[0]["agent_name"] == "Sales Bot"

    def test_get_pending_empty(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.all.return_value = []
        with patch("core.intervention_service.HITLAction", new=MagicMock()), \
             patch("core.intervention_service.AgentRegistry", new=MagicMock()):
            assert InterventionService().get_pending_interventions() == []

    def test_approve_not_found(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.intervention_service.HITLAction", new=MagicMock()):
            result = asyncio.run(InterventionService().approve_intervention("nope", "u-1"))
        assert result == {"success": False, "message": "Action not found"}

    def test_approve_not_pending(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.first.return_value = self._fake_action(status="approved")
        with patch("core.intervention_service.HITLAction", new=MagicMock()):
            result = asyncio.run(InterventionService().approve_intervention("hitl-1", "u-1"))
        assert result["success"] is False
        assert "cannot approve" in result["message"]

    def test_approve_success(self):
        db = self._db_fixture()
        action = self._fake_action()
        db.query.return_value.filter.return_value.first.return_value = action
        with patch("core.intervention_service.HITLAction", new=MagicMock()):
            result = asyncio.run(InterventionService().approve_intervention("hitl-1", "approver-9"))
        assert result == {"success": True, "message": "Action approved", "action_id": "hitl-1"}
        assert action.status == "approved"
        assert action.reviewed_by == "approver-9"
        assert action.reviewed_at is not None
        db.commit.assert_called_once()

    def test_reject_not_found(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.intervention_service.HITLAction", new=MagicMock()):
            result = asyncio.run(InterventionService().reject_intervention("nope", "u-1", "no"))
        assert result == {"success": False, "message": "Action not found"}

    def test_reject_success(self):
        db = self._db_fixture()
        action = self._fake_action()
        db.query.return_value.filter.return_value.first.return_value = action
        with patch("core.intervention_service.HITLAction", new=MagicMock()):
            result = asyncio.run(InterventionService().reject_intervention("hitl-1", "approver-9", "not now"))
        assert result["success"] is True
        assert action.status == "rejected"
        assert action.reviewed_by == "approver-9"
        assert action.user_feedback == "not now"
        db.commit.assert_called_once()


# ============================================================================
# 5. core/knowledge_query_endpoints.py
# ============================================================================


class _FakeEngine:
    def __init__(self, result):
        self.result = result
        self.queries = []

    async def query(self, ws_id, query, mode="auto"):
        self.queries.append((ws_id, query, mode))
        return self.result


@pytest.fixture
def kg_engine():
    with patch("core.service_factory.ServiceFactory.get_graphrag_engine") as m:
        engine = _FakeEngine({})
        m.return_value = engine
        yield engine


class TestKnowledgeQueryManager:
    def test_init_workspace_provided(self):
        with patch("core.service_factory.ServiceFactory.get_graphrag_engine") as m:
            mgr = KnowledgeQueryManager("ws-5")
            assert mgr.workspace_id == "ws-5"
            m.assert_called_once_with("ws-5")

    def test_init_default_workspace(self):
        with patch("core.service_factory.ServiceFactory.get_graphrag_engine") as m:
            mgr = KnowledgeQueryManager()
            assert mgr.workspace_id == "default"

    def test_answer_query_error_key(self, kg_engine):
        kg_engine.result = {"error": "graph down"}
        result = asyncio.run(KnowledgeQueryManager().answer_query("q"))
        assert "I encountered an error" in result["answer"]
        assert result["relevant_facts"] == []

    def test_answer_query_local_mode(self, kg_engine):
        kg_engine.result = {
            "mode": "local",
            "answer": "Found it",
            "entities": [{"name": f"e{i}", "type": "person", "description": f"d{i}"} for i in range(12)],
            "relationships": [{"from": "a", "type": "works_on", "to": "b"}],
        }
        result = asyncio.run(KnowledgeQueryManager("ws-1").answer_query("q", user_id="u"))
        assert result["answer"] == "Found it"
        assert result["mode"] == "local"
        assert len(result["relevant_facts"]) == 11
        assert result["relevant_facts"][0].startswith("Entity: e0")
        assert result["relevant_facts"][-1].startswith("Relationship:")

    def test_answer_query_local_mode_entity_no_description(self, kg_engine):
        kg_engine.result = {
            "mode": "local", "answer": "a",
            "entities": [{"name": "x", "type": "org"}], "relationships": [],
        }
        result = asyncio.run(KnowledgeQueryManager().answer_query("q"))
        assert result["relevant_facts"] == ["Entity: x (org) - "]

    def test_answer_query_global_mode(self, kg_engine):
        kg_engine.result = {"mode": "global", "answer": "g", "summaries": ["sum one", "sum two"]}
        result = asyncio.run(KnowledgeQueryManager().answer_query("q"))
        assert result["mode"] == "global"
        assert result["relevant_facts"] == [
            "Community Summary: sum one...", "Community Summary: sum two...",
        ]

    def test_answer_query_global_mode_no_summaries(self, kg_engine):
        kg_engine.result = {"answer": "g"}
        result = asyncio.run(KnowledgeQueryManager().answer_query("q"))
        assert result["answer"] == "g"
        assert result["relevant_facts"] == []
        assert result["mode"] is None

    def test_answer_query_default_answer(self, kg_engine):
        kg_engine.result = {"mode": "local", "entities": [], "relationships": []}
        result = asyncio.run(KnowledgeQueryManager().answer_query("q"))
        assert result["answer"] == "No answer could be synthesized."

    def test_get_knowledge_query_manager(self, kg_engine):
        mgr = get_knowledge_query_manager("ws-2")
        assert isinstance(mgr, KnowledgeQueryManager)
        assert mgr.workspace_id == "ws-2"


class TestKnowledgeQueryRoute:
    def test_route_success(self, kg_engine):
        kg_engine.result = {"mode": "global", "answer": "42", "summaries": ["s"]}
        with patch("core.knowledge_query_endpoints.get_knowledge_query_manager") as gm:
            mgr = MagicMock()
            mgr.answer_query = AsyncMock(return_value={
                "answer": "42", "relevant_facts": ["f"], "mode": "global"})
            gm.return_value = mgr
            req = KnowledgeQueryRequest(query="life", user_id="u-1", workspace_id="ws-1")
            resp = asyncio.run(knowledge_query(req, MagicMock(), MagicMock()))
        assert resp == {"success": True, "answer": "42", "relevant_facts": ["f"], "mode": "global"}

    def test_route_error_500(self, kg_engine):
        from fastapi import HTTPException
        with patch("core.knowledge_query_endpoints.get_knowledge_query_manager") as gm:
            mgr = MagicMock()
            mgr.answer_query = AsyncMock(side_effect=RuntimeError("boom"))
            gm.return_value = mgr
            req = KnowledgeQueryRequest(query="q", user_id="u-1")
            with pytest.raises(HTTPException) as ei:
                asyncio.run(knowledge_query(req, MagicMock(), MagicMock()))
        assert ei.value.status_code == 500


# ============================================================================
# 6. core/lifecycle_comm_generator.py
# ============================================================================


class TestLifecycleCommGenerator:
    def _svc(self, **overrides):
        get_byok = MagicMock()
        p = patch("core.lifecycle_comm_generator.get_byok_manager", get_byok)
        p.start()
        self._patchers = [p]
        svc = LifecycleCommGenerator(ai_service=overrides.get("ai_service"))
        return svc

    def _rule(self, **kw):
        base = {"description": "10% off", "formula": "x*0.9", "value": None, "applies_to": "General"}
        base.update(kw)
        return SimpleNamespace(**base)

    def _rules_db(self, rules):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = rules
        get_db = MagicMock()
        get_db.return_value.__enter__.return_value = db
        get_db.return_value.__exit__.return_value = False
        return patch("core.lifecycle_comm_generator.get_db_session", get_db), db

    def test_init_gets_byok_manager(self):
        svc = self._svc()
        assert svc.byok is not None
        assert svc.ai_service is None

    def test_generate_no_workspace_fallback_text(self):
        svc = self._svc()
        result = asyncio.run(svc.generate_draft("unknown", {"a": 1}))
        assert result == "Thank you for your inquiry. We are processing your request."

    def test_generate_workspace_no_rules(self):
        svc = self._svc()
        p, db = self._rules_db([])
        with p:
            result = asyncio.run(svc.generate_draft("request_quote", {"items": ["x"]}, "ws-1"))
        assert result == "Thank you for your inquiry. We are processing your request."
        db.close.assert_called_once()

    def test_generate_rules_context_formula(self):
        svc = self._svc()
        p, db = self._rules_db([self._rule()])
        with p:
            result = asyncio.run(svc.generate_draft("unknown", {}, "ws-1"))
        assert result == "Thank you for your inquiry. We are processing your request."
        db.close.assert_called_once()

    def test_generate_rules_context_value_no_applies_to(self):
        svc = self._svc()
        p, db = self._rules_db([self._rule(formula=None, value=5, applies_to=None)])
        with p:
            result = asyncio.run(svc.generate_draft("unknown", {}, "ws-1"))
        assert result == "Thank you for your inquiry. We are processing your request."

    def test_generate_ai_service_response(self):
        ai = MagicMock()
        ai.analyze_text = AsyncMock(return_value={"response": "Here is your quote"})
        svc = self._svc(ai_service=ai)
        result = asyncio.run(svc.generate_draft("offer_quote", {"quote_details": "d"}, "ws-1"))
        assert result == "Here is your quote"
        ai.analyze_text.assert_awaited_once()

    def test_generate_ai_service_missing_response_key(self):
        ai = MagicMock()
        ai.analyze_text = AsyncMock(return_value={"other": "x"})
        svc = self._svc(ai_service=ai)
        result = asyncio.run(svc.generate_draft("confirm_shipping", {}, "ws-1"))
        assert result == "I'll look into this for you."

    def test_generate_ai_service_without_analyze_text(self):
        ai = object()
        svc = self._svc(ai_service=ai)
        result = asyncio.run(svc.generate_draft("po_confirmation", {}, "ws-1"))
        assert result == "Thank you for your inquiry. We are processing your request."

    def test_prompt_request_quote(self):
        svc = self._svc()
        prompt = svc._get_prompt_for_intent("request_quote", {"items": ["widget"]})
        assert "Requesting a Quote" in prompt
        assert '["widget"]' in prompt

    def test_prompt_offer_quote(self):
        svc = self._svc()
        prompt = svc._get_prompt_for_intent("offer_quote", {"quote_details": "d", "customer_name": "C"})
        assert "Offering a Quote" in prompt
        assert "C" in prompt

    def test_prompt_confirm_shipping(self):
        svc = self._svc()
        prompt = svc._get_prompt_for_intent("confirm_shipping", {"tracking_number": "t", "carrier": "UPS", "est_delivery": "soon"})
        assert "Shipment Confirmation" in prompt
        assert "UPS" in prompt

    def test_prompt_po_confirmation(self):
        svc = self._svc()
        prompt = svc._get_prompt_for_intent("po_confirmation", {"po_id": "P1", "total_amount": "$5"})
        assert "Purchase Order Confirmation" in prompt
        assert "P1" in prompt

    def test_prompt_default(self):
        svc = self._svc()
        prompt = svc._get_prompt_for_intent("else", {"x": 1})
        assert "Context: {\"x\": 1}" in prompt


# ============================================================================
# 7. core/marketplace_usage_tracker.py
# ============================================================================


class _UsageRecord:
    """Constructor-kwarg-applying stand-in for MarketplaceUsage."""

    item_type = None
    item_id = None

    def __init__(self, **kw):
        self.__dict__.update(kw)


class TestMarketplaceUsageTracker:
    def _db_fixture(self, cm_side_effect=None):
        db = MagicMock()
        get_db = MagicMock()
        if cm_side_effect is not None:
            get_db.return_value.__enter__.side_effect = cm_side_effect
        else:
            get_db.return_value.__enter__.return_value = db
        self._patchers = [patch("core.marketplace_usage_tracker.get_db_session", get_db)]
        self._patchers[0].start()
        return db

    def test_track_usage_new_success(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.marketplace_usage_tracker.MarketplaceUsage", new=_UsageRecord):
            MarketplaceUsageTracker.track_usage("skill", "s1", success=True, duration_ms=10.0)
        usage = db.add.call_args[0][0]
        assert usage.execution_count == 1
        assert usage.success_count == 1
        assert usage.total_duration_ms == 10.0
        db.commit.assert_called_once()

    def test_track_usage_new_failure(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.first.return_value = None
        with patch("core.marketplace_usage_tracker.MarketplaceUsage", new=_UsageRecord):
            MarketplaceUsageTracker.track_usage("skill", "s2", success=False, duration_ms=5.0)
        usage = db.add.call_args[0][0]
        assert usage.execution_count == 1
        assert usage.success_count == 0

    def test_track_usage_existing_success(self):
        db = self._db_fixture()
        usage = SimpleNamespace(execution_count=3, success_count=2, total_duration_ms=30.0)
        db.query.return_value.filter.return_value.first.return_value = usage
        MarketplaceUsageTracker.track_usage("skill", "s1", success=True, duration_ms=10.0)
        assert usage.execution_count == 4
        assert usage.success_count == 3
        assert usage.total_duration_ms == 40.0
        db.add.assert_not_called()

    def test_track_usage_existing_failure(self):
        db = self._db_fixture()
        usage = SimpleNamespace(execution_count=1, success_count=1, total_duration_ms=1.0)
        db.query.return_value.filter.return_value.first.return_value = usage
        MarketplaceUsageTracker.track_usage("skill", "s1", success=False, duration_ms=2.0)
        assert usage.execution_count == 2
        assert usage.success_count == 1
        assert usage.total_duration_ms == 3.0

    def test_track_usage_error_swallowed(self):
        self._db_fixture(cm_side_effect=RuntimeError("db down"))
        MarketplaceUsageTracker.track_usage("skill", "s1")

    def test_get_pending_reports(self):
        db = self._db_fixture()
        updated = datetime(2026, 1, 1, tzinfo=timezone.utc)
        u1 = SimpleNamespace(item_type="skill", item_id="s1", execution_count=4,
                             success_count=3, total_duration_ms=200.0,
                             last_reported_at=None, updated_at=updated)
        u2 = SimpleNamespace(item_type="workflow", item_id="w1", execution_count=2,
                             success_count=2, total_duration_ms=50.0,
                             last_reported_at=updated, updated_at=None)
        db.query.return_value.filter.return_value.all.return_value = [u1, u2]
        reports = MarketplaceUsageTracker.get_pending_reports()
        assert len(reports) == 2
        assert reports[0]["avg_duration_ms"] == 50.0
        assert reports[0]["period_start"] == updated
        assert reports[1]["period_start"] == updated
        assert reports[1]["avg_duration_ms"] == 25.0
        assert u1.execution_count == 0 and u1.success_count == 0 and u1.total_duration_ms == 0.0
        assert u1.last_reported_at is not None
        assert u2.execution_count == 0
        db.commit.assert_called_once()

    def test_get_pending_reports_zero_count_safe(self):
        db = self._db_fixture()
        u = SimpleNamespace(item_type="skill", item_id="s0", execution_count=0,
                            success_count=0, total_duration_ms=0.0,
                            last_reported_at=None, updated_at=None)
        db.query.return_value.filter.return_value.all.return_value = [u]
        reports = MarketplaceUsageTracker.get_pending_reports()
        assert reports[0]["avg_duration_ms"] == 0

    def test_get_pending_reports_empty(self):
        db = self._db_fixture()
        db.query.return_value.filter.return_value.all.return_value = []
        assert MarketplaceUsageTracker.get_pending_reports() == []

    def test_get_pending_reports_error_swallowed(self):
        self._db_fixture(cm_side_effect=RuntimeError("db down"))
        assert MarketplaceUsageTracker.get_pending_reports() == []


# ============================================================================
# 8. core/memory_integration_mixin.py
# ============================================================================


class _FakeMixin(MemoryIntegrationMixin):
    def __init__(self, records=None, fetch_error=None, integration_id="outlook", **kw):
        super().__init__(integration_id=integration_id, **kw)
        self._records = records or []
        self._fetch_error = fetch_error

    async def fetch_records(self, start_date=None, end_date=None, limit=500):
        if self._fetch_error:
            raise self._fetch_error
        return self._records


class _FakeTask:
    """Stand-in for asyncio.Task to drive handle_error branches."""

    def __init__(self, exc_mode="exception"):
        self.exc_mode = exc_mode
        self.callback = None
        self.cancelled = False

    def add_done_callback(self, cb):
        self.callback = cb

    def exception(self):
        if self.exc_mode == "cancelled":
            raise asyncio.CancelledError()
        if self.exc_mode == "handler_error":
            raise RuntimeError("handler boom")
        return Exception("boom") if self.exc_mode == "exception" else None

    def done(self):
        return False

    def cancel(self):
        self.cancelled = True
        return True


@pytest.fixture
def mixin_env():
    """Patch EmbeddingService, IntegrationEntityExtractor, lancedb handler."""
    with patch("core.memory_integration_mixin.EmbeddingService") as es, \
         patch("core.memory_integration_mixin.IntegrationEntityExtractor") as ie, \
         patch.dict(os.environ, {"ENABLE_LLM_EXTRACTION": "false"}):
        es.return_value.generate_embedding = MagicMock(return_value=[0.1, 0.2])
        ie.return_value.extract = AsyncMock(return_value=[])
        yield SimpleNamespace(embedding=es, extractor=ie)


class TestBackfillJob:
    def test_defaults(self):
        job = BackfillJob("j1", "outlook")
        assert job.status == "pending"
        assert job.progress == 0
        assert job.started_at is None and job.completed_at is None
        assert job.error is None and job.task is None

    def test_to_dict_without_dates(self):
        job = BackfillJob("j1", "outlook")
        d = job.to_dict()
        assert d["job_id"] == "j1"
        assert d["started_at"] is None and d["completed_at"] is None

    def test_to_dict_with_dates(self):
        job = BackfillJob("j1", "outlook")
        job.status = "completed"
        job.progress = 100
        job.started_at = datetime(2026, 1, 1)
        job.completed_at = datetime(2026, 1, 2)
        job.error = None
        d = job.to_dict()
        assert d["status"] == "completed"
        assert d["started_at"] == "2026-01-01T00:00:00"
        assert d["completed_at"] == "2026-01-02T00:00:00"


class TestMixinInit:
    def test_init_success(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler") as gl:
            ldb = MagicMock()
            gl.return_value = ldb
            mixin = _FakeMixin(integration_id="outlook")
        assert mixin.integration_id == "outlook"
        assert mixin.workspace_id == "default"
        assert mixin.lancedb is ldb
        assert mixin.use_llm_extraction is False

    def test_init_lancedb_import_error(self, mixin_env):
        with patch.dict(sys.modules, {"core.lancedb_handler": None}):
            mixin = _FakeMixin(integration_id="gmail")
        assert mixin.lancedb is None

    def test_init_llm_extraction_env_true(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"), \
             patch.dict(os.environ, {"ENABLE_LLM_EXTRACTION": "true"}):
            mixin = _FakeMixin(integration_id="gmail")
        assert mixin.use_llm_extraction is True

    def test_init_workspace_id(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler") as gl:
            mixin = _FakeMixin(integration_id="gmail", workspace_id="ws-7")
        gl.assert_called_once_with("ws-7")


class TestGetIntegrationType:
    @pytest.mark.parametrize("iid,expected", [
        ("outlook", "email"), ("gmail", "email"), ("email", "email"),
        ("salesforce", "crm"), ("hubspot", "crm"), ("zoho", "crm"), ("pipedrive", "crm"),
        ("slack", "communication"), ("teams", "communication"), ("discord", "communication"),
        ("jira", "project"), ("asana", "project"), ("notion", "project"),
        ("trello", "project"), ("monday", "project"),
        ("zendesk", "support"), ("intercom", "support"), ("freshdesk", "support"),
        ("google_calendar", "calendar"), ("outlook_calendar", "calendar"), ("calendar", "calendar"),
        ("custom", "other"),
    ])
    def test_all_categories(self, mixin_env, iid, expected):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin(integration_id=iid)
        assert mixin.get_integration_type() == expected

    def test_case_insensitive(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin(integration_id="Outlook")
        assert mixin.get_integration_type() == "email"


class TestBackfillToMemory:
    def test_returns_started_response(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin()
            result = asyncio.run(mixin.backfill_to_memory())
        assert result["success"] is True
        assert result["status"] == "started"
        assert result["integration_id"] == "outlook"
        assert result["job_id"]

    def test_real_task_completes_no_records(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin()
            result = asyncio.run(mixin.backfill_to_memory())
        job = _backfill_jobs[result["job_id"]]
        for _ in range(5):
            asyncio.run(asyncio.sleep(0))
        assert job.status == "completed"
        assert job.progress == 100
        d = mixin.get_job_status(result["job_id"])
        assert d["status"] == "completed"

    def test_get_job_status_missing(self, mixin_env):
        assert _FakeMixin.get_job_status("missing") is None

    def test_abstract_fetch_records_base_impl(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin()
        assert asyncio.run(MemoryIntegrationMixin.fetch_records(mixin, None, None, 10)) is None

    def test_handle_error_failed_branch(self, mixin_env):
        fake = _FakeTask(exc_mode="exception")
        with patch("core.lancedb_handler.get_lancedb_handler"), \
             patch("core.memory_integration_mixin.asyncio.create_task", return_value=fake):
            mixin = _FakeMixin()
            result = asyncio.run(mixin.backfill_to_memory())
        job = _backfill_jobs[result["job_id"]]
        fake.callback(fake)
        assert job.status == "failed"
        assert job.error == "boom"
        assert job.completed_at is not None
        assert fake.cancelled is True

    def test_handle_error_cancelled_branch(self, mixin_env):
        fake = _FakeTask(exc_mode="cancelled")
        with patch("core.lancedb_handler.get_lancedb_handler"), \
             patch("core.memory_integration_mixin.asyncio.create_task", return_value=fake):
            mixin = _FakeMixin()
            result = asyncio.run(mixin.backfill_to_memory())
        job = _backfill_jobs[result["job_id"]]
        fake.callback(fake)
        assert job.status == "cancelled"
        assert job.completed_at is not None

    def test_handle_error_unexpected_branch(self, mixin_env):
        fake = _FakeTask(exc_mode="handler_error")
        with patch("core.lancedb_handler.get_lancedb_handler"), \
             patch("core.memory_integration_mixin.asyncio.create_task", return_value=fake):
            mixin = _FakeMixin()
            result = asyncio.run(mixin.backfill_to_memory())
        job = _backfill_jobs[result["job_id"]]
        fake.callback(fake)
        assert job.status == "failed"
        assert job.error == "Handler error: handler boom"


class TestRunBackfill:
    def test_fetch_error_marks_failed(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin(fetch_error=RuntimeError("api down"))
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 500, 50))
        assert job.status == "failed"
        assert job.error == "api down"
        assert job.completed_at is not None

    def test_no_records_completes(self, mixin_env):
        with patch("core.lancedb_handler.get_lancedb_handler"):
            mixin = _FakeMixin(records=[])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 500, 50))
        assert job.status == "completed"
        assert job.progress == 100
        assert job.total_records == 0

    def test_happy_path_entities_stored(self, mixin_env):
        records = [{"id": f"r{i}", "subject": f"subject {i}", "from": "a@x.com",
                    "body": "body text here"} for i in range(5)]
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "this is a long enough text to embed"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb):
            mixin = _FakeMixin(records=records)
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 5, 5))
        assert job.status == "completed"
        assert job.progress == 100
        assert job.processed_records == 1
        assert job.failed_records == 0
        ldb.add_documents.assert_awaited_once()

    def test_entity_missing_id_skipped(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = [
            {"text": "this is a long enough text to embed"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb):
            mixin = _FakeMixin(records=[{"id": "r1"}])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.failed_records == 1
        assert ldb.add_documents.await_count == 0

    def test_entity_short_text_skipped(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "short"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb):
            mixin = _FakeMixin(records=[{"id": "r1"}])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.failed_records == 1
        assert ldb.add_documents.await_count == 0

    def test_add_documents_retry_then_success(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "this is a long enough text to embed"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock(side_effect=[RuntimeError("db"), None])
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb), \
             patch("core.memory_integration_mixin.asyncio.sleep", new=AsyncMock()):
            mixin = _FakeMixin(records=[{"id": "r1"}])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.processed_records == 1
        assert job.failed_records == 0
        assert ldb.add_documents.await_count == 2

    def test_add_documents_always_fails(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "this is a long enough text to embed"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock(side_effect=[RuntimeError("db")] * 3)
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb), \
             patch("core.memory_integration_mixin.asyncio.sleep", new=AsyncMock()):
            mixin = _FakeMixin(records=[{"id": "r1"}])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.processed_records == 0
        assert job.failed_records == 1

    def test_embedding_error_counts_failed(self, mixin_env):
        mixin_env.embedding.return_value.generate_embedding.side_effect = RuntimeError("emb down")
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "this is a long enough text to embed"}
        ]
        ldb = MagicMock()
        ldb.add_documents = AsyncMock()
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=ldb):
            mixin = _FakeMixin(records=[{"id": "r1"}])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.failed_records == 1

    def test_no_lancedb_skips_storage(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = [
            {"id": "e1", "text": "this is a long enough text to embed"}
        ]
        with patch("core.lancedb_handler.get_lancedb_handler") as gl:
            gl.side_effect = ImportError("no lancedb")
            mixin = _FakeMixin(records=[{"id": "r1"}])
        assert mixin.lancedb is None
        job = BackfillJob("j1", "outlook")
        asyncio.run(mixin._run_backfill(job, None, None, 1, 1))
        assert job.status == "completed"

    def test_multiple_batches_progress(self, mixin_env):
        mixin_env.extractor.return_value.extract.return_value = []
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=MagicMock()):
            mixin = _FakeMixin(records=[{"id": f"r{i}"} for i in range(10)])
            job = BackfillJob("j1", "outlook")
            asyncio.run(mixin._run_backfill(job, None, None, 10, 3))
        assert job.status == "completed"
        assert job.progress == 100


class TestIntegrationBackfillManager:
    def test_trigger_backfill_unsupported(self, mixin_env):
        result = asyncio.run(IntegrationBackfillManager.trigger_backfill("notreal"))
        assert result["success"] is False
        assert "not supported" in result["error"]

    def test_trigger_backfill_success(self, mixin_env):
        fake_module = MagicMock()
        svc = MagicMock()
        svc.backfill_to_memory = AsyncMock(return_value={"success": True, "job_id": "j-1"})
        fake_module.OutlookIntegration.return_value = svc
        with patch("builtins.__import__", return_value=fake_module):
            result = asyncio.run(IntegrationBackfillManager.trigger_backfill("outlook"))
        assert result == {"success": True, "job_id": "j-1"}
        svc.backfill_to_memory.assert_awaited_once()

    def test_trigger_backfill_exception(self, mixin_env):
        fake_module = MagicMock()
        svc = MagicMock()
        svc.backfill_to_memory = AsyncMock(side_effect=RuntimeError("fail"))
        fake_module.GmailService.return_value = svc
        with patch("builtins.__import__", return_value=fake_module):
            result = asyncio.run(IntegrationBackfillManager.trigger_backfill("gmail"))
        assert result["success"] is False
        assert "fail" in result["error"]

    def test_trigger_all_backfills(self, mixin_env):
        calls = []

        async def fake_trigger(iid, start_date=None, end_date=None, limit=500):
            calls.append(iid)
            if iid == "gmail":
                return {"success": True, "job_id": "j-gmail"}
            if iid == "salesforce":
                return {"success": False, "error": "no service"}
            raise RuntimeError("unexpected")

        with patch.object(IntegrationBackfillManager, "trigger_backfill", side_effect=fake_trigger):
            result = asyncio.run(IntegrationBackfillManager.trigger_all_backfills())
        assert result["success"] is True
        assert result["total_triggered"] == 1
        assert result["job_ids"] == ["j-gmail"]
        assert len(result["errors"]) == 7
        assert "salesforce: no service" in result["errors"]
        assert len(calls) == 8


# ============================================================================
# 9. core/meta_automation.py
# ============================================================================


class TestMetaAutomationEngine:
    def test_fallback_registry_populated(self):
        engine = MetaAutomationEngine()
        assert engine.fallback_registry["salesforce"] == "CRMManualOperator"
        assert "hubspot" in engine.fallback_registry
        assert engine.fallback_registry["remote_market"] == "MarketplaceAdminWorkflow"
        assert engine.fallback_registry["supplier_portal"] == "LogisticsManagerWorkflow"

    @pytest.mark.parametrize("msg,expected", [
        ("Server error 500 occurred", True),
        ("503 Service Unavailable", True),
        ("429 rate limit", True),
        ("API not implemented", True),
        ("feature missing in endpoint", True),
        ("connection reset by peer", True),
        ("request timeout", True),
        ("some unrelated error", False),
        ("", False),
    ])
    def test_should_fallback(self, msg, expected):
        assert MetaAutomationEngine().should_fallback(Exception(msg)) is expected

    def test_get_fallback_agent_known_lowercase(self):
        assert MetaAutomationEngine().get_fallback_agent("SalesForce") == "CRMManualOperator"

    def test_get_fallback_agent_unknown(self):
        assert MetaAutomationEngine().get_fallback_agent("dropbox") is None

    def test_execute_fallback_unknown_agent(self):
        result = MetaAutomationEngine().execute_fallback("dropbox", "goal", {})
        assert result["status"] == "failed"
        assert "No fallback agent" in result["error"]

    def test_execute_fallback_marketplace_price(self):
        mod = types.ModuleType("operations.automations.marketplace_admin")
        agent_cls = MagicMock()
        agent = MagicMock()
        agent.update_listing_price = MagicMock(return_value={"status": "success", "price_updated": True})
        agent_cls.return_value = agent
        mod.MarketplaceAdminWorkflow = agent_cls
        with patch.dict(sys.modules, {"operations.automations.marketplace_admin": mod}):
            result = MetaAutomationEngine().execute_fallback("remote_market", "update price for SKU-1", {"sku": "SKU-1", "price": "19.99"})
        assert result == {"status": "success", "price_updated": True}
        agent.update_listing_price.assert_called_once_with("SKU-1", "19.99")

    def test_execute_fallback_marketplace_defaults_no_price(self):
        mod = types.ModuleType("operations.automations.marketplace_admin")
        agent_cls = MagicMock()
        agent = MagicMock()
        agent.update_listing_price = MagicMock(return_value={"status": "success"})
        agent_cls.return_value = agent
        mod.MarketplaceAdminWorkflow = agent_cls
        with patch.dict(sys.modules, {"operations.automations.marketplace_admin": mod}):
            result = MetaAutomationEngine().execute_fallback("remote_market", "hello", {})
        assert result["status"] == "success"

    def test_execute_fallback_marketplace_import_error(self):
        with patch.dict(sys.modules, {"operations.automations.marketplace_admin": None}):
            result = MetaAutomationEngine().execute_fallback("remote_market", "update price", {})
        assert result["status"] == "failed"
        assert "Agent Execution Failed" in result["error"]

    def test_execute_fallback_logistics_order(self):
        mod = types.ModuleType("operations.automations.logistics_manager")
        agent_cls = MagicMock()
        agent = MagicMock()
        agent.place_purchase_order = MagicMock(return_value={"status": "success", "po": "PO-1"})
        agent_cls.return_value = agent
        mod.LogisticsManagerWorkflow = agent_cls
        with patch.dict(sys.modules, {"operations.automations.logistics_manager": mod}):
            result = MetaAutomationEngine().execute_fallback("supplier_portal", "place order for 5", {"sku": "S", "qty": "5"})
        assert result == {"status": "success", "po": "PO-1"}
        agent.place_purchase_order.assert_called_once_with("S", "5")

    def test_execute_fallback_logistics_no_order_defaults(self):
        mod = types.ModuleType("operations.automations.logistics_manager")
        agent_cls = MagicMock()
        agent = MagicMock()
        agent.place_purchase_order = MagicMock(return_value={"status": "success"})
        agent_cls.return_value = agent
        mod.LogisticsManagerWorkflow = agent_cls
        with patch.dict(sys.modules, {"operations.automations.logistics_manager": mod}):
            result = MetaAutomationEngine().execute_fallback("supplier_portal", "status check", {})
        assert result["status"] == "success"

    def test_execute_fallback_logistics_import_error(self):
        with patch.dict(sys.modules, {"operations.automations.logistics_manager": None}):
            result = MetaAutomationEngine().execute_fallback("supplier_portal", "place order", {})
        assert result["status"] == "failed"
        assert "Agent Execution Failed" in result["error"]

    def test_execute_fallback_default_mock_response(self):
        result = MetaAutomationEngine().execute_fallback("salesforce", "fix the data", {})
        assert result["status"] == "success"
        assert result["agent"] == "CRMManualOperator"
        assert "Simulated Visual Interaction" in result["action"]

    def test_get_meta_automation_factory(self):
        engine = get_meta_automation()
        assert isinstance(engine, MetaAutomationEngine)


# ============================================================================
# 10. core/model_factory.py
# ============================================================================


class TestModelFactory:
    def test_type_map_complete(self):
        assert ModelFactory.TYPE_MAP["string"] is str
        assert ModelFactory.TYPE_MAP["integer"] is int
        assert ModelFactory.TYPE_MAP["number"] is float
        assert ModelFactory.TYPE_MAP["boolean"] is bool
        assert ModelFactory.TYPE_MAP["array"] is list
        assert ModelFactory.TYPE_MAP["object"] is dict
        assert ModelFactory.TYPE_MAP["null"] is type(None)

    def test_create_pydantic_model_basic(self):
        factory = ModelFactory()
        model = factory.create_pydantic_model(
            "t1", "Invoice", {
                "type": "object",
                "required": ["amount"],
                "properties": {
                    "amount": {"type": "number", "description": "Total"},
                    "note": {"type": "string", "description": "Note"},
                },
            }, extra_ignored=True)
        assert model.__name__ == "Invoice"
        inst = model(amount=10.5)
        assert inst.amount == 10.5
        assert inst.note is None
        assert model.model_fields["amount"].description == "Total"
        with pytest.raises(Exception):
            model()

    def test_create_model_required_fields(self):
        factory = ModelFactory()
        model = factory._create_model_from_schema("X", {
            "required": ["a", "b"],
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "integer", "description": "b desc"},
            },
        })
        inst = model(a="x", b=1)
        assert inst.a == "x" and inst.b == 1

    def test_create_model_no_properties(self):
        factory = ModelFactory()
        model = factory._create_model_from_schema("Empty", {"type": "object"})
        inst = model()
        assert inst is not None

    def test_create_model_no_required(self):
        factory = ModelFactory()
        model = factory._create_model_from_schema("Y", {
            "properties": {"opt": {"type": "string"}},
        })
        assert model(opt="v").opt == "v"

    @pytest.mark.parametrize("field_def,expected", [
        ({"type": "string"}, str),
        ({"type": "integer"}, int),
        ({"type": "number"}, float),
        ({"type": "boolean"}, bool),
        ({"type": "array"}, list),
        ({"type": "object"}, dict),
        ({"type": "null"}, type(None)),
        ({"type": "uuid"}, str),
        ({}, str),
    ])
    def test_map_scalar_types(self, field_def, expected):
        assert ModelFactory()._map_json_type_to_python(field_def) is expected

    def test_map_nullable_list(self):
        import typing
        mapped = ModelFactory()._map_json_type_to_python({"type": ["string", "null"]})
        assert mapped == typing.Optional[str]

    def test_map_list_without_null(self):
        assert ModelFactory()._map_json_type_to_python({"type": ["integer", "string"]}) is int

    def test_map_list_only_null(self):
        import typing
        mapped = ModelFactory()._map_json_type_to_python({"type": ["null"]})
        assert mapped == typing.Optional[str]

    def test_map_empty_list(self):
        assert ModelFactory()._map_json_type_to_python({"type": []}) is str

    def test_invalidate_cache(self):
        assert ModelFactory().invalidate_cache("t1", "entity") == 0

    def test_get_model_factory_singleton(self):
        with patch("core.model_factory._model_factory", None):
            a = get_model_factory()
            b = get_model_factory()
            assert a is b
            assert isinstance(a, ModelFactory)
            assert a.cache is not None

    def test_model_optional_field_default_none(self):
        factory = ModelFactory()
        model = factory._create_model_from_schema("Z", {
            "properties": {"maybe": {"type": "string"}},
        })
        assert model().maybe is None
