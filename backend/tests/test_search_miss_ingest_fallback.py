"""Search-miss → on-demand ingest fallback (live 2026-09-11, Seguin
incident, part 3): the agent answered "no such email — forward it to me"
while the message sat in the mailbox. The ingest leg existed but only
fired when the planner LLM happened to plan intent=ingest. These tests pin
the automatic behavior:

1. resolution climbs figure-phrase → sender-scoped → per-term →
   search-free recent-window forms (the fallback must be able to find a
   target with the SAME forms that search uses, plus one that cannot
   fail the way $search does);
2. the outlook leg auto-ingests on a total miss and re-searches;
3. the universal leg auto-ingests for any searchable service;
4. gates hold: kill switch or autonomy approval → a note, never a write.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import core.chat_tool_planner as ctp
from core.chat_tool_planner import (
    ToolPlan,
    _mailbox_ingest_core,
    _resolve_mailbox_message_ids,
    execute_tool_plan,
)


SEGUIN_MSG = {
    "id": "seguin-fw-rfq",
    "subject": "FW: RFQ - Foot shear",
    "body_preview": "$ 5,350.00 – 10 %  in stock Do you prefer a used shear ?",
    "body": None,
    "sender": {"emailAddress": {"address": "joelseguin@seguinmach.com"}},
    "from_field": {"emailAddress": {"address": "joelseguin@seguinmach.com"}},
    "received_date_time": "2026-08-26T14:06:28Z",
}
QUERY = 'joelseguin@seguinmach.com "$ 5,350.00 – 10 %  in stock"'


def _plan(service="outlook", intent="search", query=QUERY):
    return ToolPlan(use_tool=True, service=service, intent=intent, query=query)


# --- resolution ladder -------------------------------------------------------


def test_resolve_uses_figure_phrase_first():
    async def harness():
        calls = []

        async def fake_search(user_id, query, max_results=10, quote=False, sender=None, token=None):
            calls.append({"query": query, "quote": quote, "sender": sender})
            if quote and "5,350.00" in query:
                return [SEGUIN_MSG]
            return []

        import integrations.outlook_service as osvc

        with patch.object(osvc.outlook_service, "search_emails",
                          AsyncMock(side_effect=fake_search)):
            ids = await _resolve_mailbox_message_ids("outlook", "u-1", QUERY)
        return calls, ids

    calls, ids = asyncio.run(harness())
    assert ids == ["seguin-fw-rfq"]
    # first form tried was the exact amount phrase
    assert calls[0]["query"] == "5,350.00" and calls[0]["quote"] is True


def test_resolve_falls_through_to_recent_window_when_all_search_misses():
    async def harness():
        import integrations.outlook_service as osvc

        async def empty_search(*a, **k):
            return []

        async def fake_recent(user_id, max_results=50, token=None):
            return [SEGUIN_MSG, {
                "id": "unrelated", "subject": "Lunch?",
                "body_preview": "werewolf movie night", "body": None,
                "sender": {"emailAddress": {"address": "friend@example.com"}},
                "from_field": {"emailAddress": {"address": "friend@example.com"}},
                "received_date_time": "2026-08-27T10:00:00Z",
            }]

        with patch.object(osvc.outlook_service, "search_emails",
                          AsyncMock(side_effect=empty_search)), \
             patch.object(osvc.outlook_service, "list_recent_emails",
                          AsyncMock(side_effect=fake_recent)):
            ids = await _resolve_mailbox_message_ids(
                "outlook", "u-1", "the seguin 5,350.00 quote")
        return ids

    ids = asyncio.run(harness())
    assert ids == ["seguin-fw-rfq"], "recent-window scan must pick the figure match"


# --- mailbox core + outlook leg fallback -------------------------------------


def test_mailbox_core_blocked_by_gate_never_ingests(monkeypatch):
    async def harness():
        with patch.object(ctp, "_planner_ingest_enabled", lambda: True), \
             patch("tools.email_attachment_tool._gate",
                   return_value={"reason": "owner pinned review"}), \
             patch("integrations.atom_communication_ingestion_pipeline.ingestion_pipeline",
                   None) as _:
            core = await _mailbox_ingest_core("outlook", "u-1", QUERY, {})
        return core

    core = asyncio.run(harness())
    assert core["blocked"] == "owner pinned review"
    assert core["ingested_count"] == 0


def test_mailbox_core_ingests_and_counts(monkeypatch):
    async def harness():
        async def fake_resolve(service, user_id, query, limit=2, **kw):
            return ["seguin-fw-rfq"]

        fake_pipeline = SimpleNamespace()
        fake_pipeline.ingest_email_on_demand = AsyncMock(return_value={
            "status": "ingested", "subject": "FW: RFQ - Foot shear",
            "attachments": 0})

        class _Pipe:
            ingest_email_on_demand = staticmethod(fake_pipeline.ingest_email_on_demand)

        with patch.object(ctp, "_planner_ingest_enabled", lambda: True), \
             patch.object(ctp, "_resolve_mailbox_message_ids", fake_resolve), \
             patch("tools.email_attachment_tool._gate", return_value=None), \
             patch("integrations.atom_communication_ingestion_pipeline.ingestion_pipeline",
                   _Pipe):
            core = await _mailbox_ingest_core(
                "outlook", "u-1",
                'seguin "5,350.00"', {})
        return core, fake_pipeline

    core, fake_pipeline = asyncio.run(harness())
    assert core["blocked"] is None
    assert core["ingested_count"] == 1
    fake_pipeline.ingest_email_on_demand.assert_awaited_once()


def test_outlook_leg_empty_search_triggers_ingest_and_research(monkeypatch):
    """The incident, end to end at the leg level: live search empty, store
    empty → ingest core pulls the message → re-search finds it → the block
    carries the ON-DEMAND PULL note and the evidence."""
    state = {"searches": 0}

    async def fake_search(user_id, query, max_results=10, quote=False, sender=None, token=None):
        state["searches"] += 1
        if state["searches"] > 6:  # after the fallback re-run
            return [SEGUIN_MSG]
        return []

    async def fake_store_lines(user_id, query, context=None, **kw):
        return []

    async def fake_ingest_core(service, user_id, query, context, *, progress=None,
                               skip_provider_query=False):
        return {"blocked": None, "ingested_count": 1,
                "lines": ["- message seguin-fw-rfq… INGESTED | subject: FW: RFQ - Foot shear"]}

    async def fake_full_bodies(user_id, emails, n, cap):
        return {}

    async def fake_memory(user_id, query, context):
        return None

    monkeypatch.setattr("integrations.outlook_service.outlook_service.search_emails",
                        AsyncMock(side_effect=fake_search))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", fake_store_lines)
    monkeypatch.setattr(ctp, "_mailbox_ingest_core", fake_ingest_core)
    monkeypatch.setattr(ctp, "_outlook_full_bodies", fake_full_bodies)
    monkeypatch.setattr(ctp, "_memory_search_block", fake_memory)
    monkeypatch.setattr(ctp, "_latest_styled_ingested", lambda *a, **k: None)
    monkeypatch.setattr(ctp, "_graph_styled_fallback", lambda emails: None)

    block = asyncio.run(execute_tool_plan(_plan(), "u-1", context={"history": []}))

    assert block is not None
    assert "ON-DEMAND PULL" in block
    assert "INGESTED" in block
    assert "FW: RFQ - Foot shear" in block


def test_outlook_leg_blocked_ingest_still_honest_dead_end(monkeypatch):
    async def empty(*a, **k):
        return []

    async def fake_ingest_core(service, user_id, query, context, *, progress=None,
                               skip_provider_query=False):
        return {"blocked": "owner pinned review", "lines": [], "ingested_count": 0}

    monkeypatch.setattr("integrations.outlook_service.outlook_service.search_emails",
                        AsyncMock(side_effect=empty))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", empty)
    monkeypatch.setattr(ctp, "_mailbox_ingest_core", fake_ingest_core)
    monkeypatch.setattr(ctp, "_memory_search_block", empty)

    block = asyncio.run(execute_tool_plan(_plan(), "u-1", context={"history": []}))
    assert "no matching messages" in block
    assert "needs owner approval" in block


# --- universal leg fallback ---------------------------------------------------


def test_universal_leg_empty_search_ingests_and_reruns(monkeypatch):
    calls = {"search": 0}

    async def fake_search(self, service, query, context=None):
        calls["search"] += 1
        if calls["search"] >= 2:
            return {"status": "success", "data": [{"id": "rec-1", "name": "Acme lead"}]}
        return {"status": "success", "data": []}

    async def fake_ing_core(service, user_id, query, context, *, progress=None):
        assert service == "zoho_crm"
        return {"blocked": None, "ingested_count": 2,
                "lines": ["- lead-1 INGESTED", "- lead-2 INGESTED"], "raw": None}

    monkeypatch.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService.search",
        fake_search)
    monkeypatch.setattr(ctp, "_integration_ingest_core", fake_ing_core)
    monkeypatch.setattr(ctp, "_memory_search_block", AsyncMock(return_value=None))

    block = asyncio.run(execute_tool_plan(
        _plan(service="zoho_crm", query="acme"), "u-1", context={"history": []}))

    assert calls["search"] == 2, "search must re-run after the pull"
    assert "ON-DEMAND PULL" in block
    assert "Acme lead" in block


def test_universal_leg_nothing_upstream_still_dead_end(monkeypatch):
    async def fake_search(self, service, query, context=None):
        return {"status": "success", "data": []}

    async def fake_ing_core(service, user_id, query, context, *, progress=None):
        return {"blocked": None, "ingested_count": 0,
                "lines": ["- nothing ingested (no matching item found)"], "raw": None}

    monkeypatch.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService.search",
        fake_search)
    monkeypatch.setattr(ctp, "_integration_ingest_core", fake_ing_core)
    monkeypatch.setattr(ctp, "_memory_search_block", AsyncMock(return_value=None))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", AsyncMock(return_value=[]))

    block = asyncio.run(execute_tool_plan(
        _plan(service="zoho_crm", query="ghost-co"), "u-1", context={"history": []}))

    assert "returned nothing usable" in block
    assert "found nothing upstream" in block


# --- P1-1: internal budget — a slow pull degrades to the miss path -------


def test_slow_pull_times_out_to_miss_path_with_honest_note(monkeypatch):
    """A pull slower than the fallback's INTERNAL budget must degrade to
    the pre-fallback miss path with an honest note — never an unhandled
    TimeoutError, never a caller-budget blowout, never a silent write."""
    monkeypatch.setattr(ctp, "_INGEST_FALLBACK_BUDGET_SECONDS", 0.2)

    async def empty(*a, **k):
        return []

    pull_calls = []

    async def slow_ingest_core(service, user_id, query, context, *,
                               progress=None, skip_provider_query=False):
        pull_calls.append(query)
        await asyncio.sleep(5)  # far beyond the 0.2s budget
        raise AssertionError("must be cancelled before finishing")

    async def fake_memory(user_id, query, context):
        return None

    monkeypatch.setattr(
        "integrations.outlook_service.outlook_service.search_emails",
        AsyncMock(side_effect=empty))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", empty)
    monkeypatch.setattr(ctp, "_mailbox_ingest_core", slow_ingest_core)
    monkeypatch.setattr(ctp, "_memory_search_block", fake_memory)

    import time

    t0 = time.monotonic()
    block = asyncio.run(execute_tool_plan(_plan(), "u-1", context={"history": []}))
    elapsed = time.monotonic() - t0

    assert block is not None
    assert "no matching messages" in block
    assert "internal time budget" in block, block
    assert "do not claim the content does not exist" in block
    assert elapsed < 3, f"lane budget blown by the slow pull ({elapsed:.1f}s)"
    assert pull_calls, "the fallback must have FIRED before timing out"


def test_slow_pull_that_landed_reports_it_honestly(monkeypatch):
    """If the checkpoint proves content landed before the budget expired,
    the note must say exactly that (never a silent write)."""
    monkeypatch.setattr(ctp, "_INGEST_FALLBACK_BUDGET_SECONDS", 0.2)

    async def empty(*a, **k):
        return []

    async def partial_ingest_core(service, user_id, query, context, *,
                                  progress=None, skip_provider_query=False):
        # First message landed, second one hangs.
        progress.setdefault("landed", []).append(
            "- message seguin-fw-rfq… in memory (ingested) | subject: FW: RFQ")
        await asyncio.sleep(5)

    monkeypatch.setattr(
        "integrations.outlook_service.outlook_service.search_emails",
        AsyncMock(side_effect=empty))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", empty)
    monkeypatch.setattr(ctp, "_mailbox_ingest_core", partial_ingest_core)
    monkeypatch.setattr(ctp, "_memory_search_block", AsyncMock(return_value=None))

    block = asyncio.run(execute_tool_plan(_plan(), "u-1", context={"history": []}))

    assert "ON-DEMAND PULL (partial)" in block
    assert "WAS pulled into memory" in block
    assert "FW: RFQ" in block


def test_universal_leg_slow_pull_degrades_the_same_way(monkeypatch):
    monkeypatch.setattr(ctp, "_INGEST_FALLBACK_BUDGET_SECONDS", 0.2)

    async def fake_search(self, service, query, context=None):
        return {"status": "success", "data": []}

    async def slow_ing_core(service, user_id, query, context, *, progress=None):
        progress["started"] = True
        await asyncio.sleep(5)

    monkeypatch.setattr(
        "integrations.universal_integration_service.UniversalIntegrationService.search",
        fake_search)
    monkeypatch.setattr(ctp, "_integration_ingest_core", slow_ing_core)
    monkeypatch.setattr(ctp, "_memory_search_block", AsyncMock(return_value=None))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", AsyncMock(return_value=[]))

    block = asyncio.run(execute_tool_plan(
        _plan(service="zoho_crm", query="acme"), "u-1", context={"history": []}))

    assert "returned nothing usable" in block
    assert "internal time budget" in block, block


# --- P3-13: one attempt per turn, enforced by STATE -----------------------


def test_second_execute_in_same_context_does_not_repull(monkeypatch):
    """The one-attempt bound must live on the context, not on singleflight:
    a second execute_tool_plan with the SAME context dict must not pull."""
    pulls = []

    async def empty(*a, **k):
        return []

    async def fake_ing_core(service, user_id, query, context, *,
                            progress=None, skip_provider_query=False):
        pulls.append(query)
        return {"blocked": None, "ingested_count": 0, "lines": []}

    monkeypatch.setattr(
        "integrations.outlook_service.outlook_service.search_emails",
        AsyncMock(side_effect=empty))
    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", empty)
    monkeypatch.setattr(ctp, "_mailbox_ingest_core", fake_ing_core)
    monkeypatch.setattr(ctp, "_memory_search_block", AsyncMock(return_value=None))

    ctx = {"history": []}
    first = asyncio.run(execute_tool_plan(_plan(), "u-1", context=ctx))
    second = asyncio.run(execute_tool_plan(_plan(), "u-1", context=ctx))

    assert pulls, "the first turn must pull"
    assert len(pulls) == 1, f"second turn re-pulled: {pulls}"
    assert ctx["_ingest_attempted"] is True
    assert "no matching messages" in first
    assert "no matching messages" in second


# --- P2-7: gmail gets a search-free resolution rung ------------------------


class _FakeGmailService:
    """Stands in for GmailService at the resolver's import site."""

    instances = []

    def __init__(self):
        self.service = object()  # truthy: no _authenticate path
        self.calls = []
        _FakeGmailService.instances.append(self)

    def get_messages(self, query="", max_results=50, **kw):
        self.calls.append({"q": query, "max": max_results})
        if query:
            return []  # the provider search that already missed
        return [
            {
                "id": "gmail-seguin-1",
                "subject": "FW: RFQ - Foot shear",
                "snippet": "$ 5,350.00 – 10 % in stock",
                "sender": "joelseguin@seguinmach.com",
            },
            {
                "id": "gmail-unrelated",
                "subject": "Lunch?",
                "snippet": "werewolf movie night",
                "sender": "friend@example.com",
            },
        ]


def test_gmail_recent_window_rung_resolves_by_figure_token(monkeypatch):
    """Rung 4 for gmail: newest-N listing + the SHARED local matcher — the
    fallback used to dead-end at 'no candidate' after a duplicate provider
    search."""
    import integrations.gmail_service as gs

    monkeypatch.setattr(gs, "GmailService", _FakeGmailService)

    ids = asyncio.run(
        ctp._resolve_mailbox_message_ids(
            "gmail", "u-1", "the seguin 5,350.00 quote", skip_provider_query=True)
    )

    assert ids == ["gmail-seguin-1"]
    svc = _FakeGmailService.instances[-1]
    assert svc.calls, "the search-free listing must run"
    assert all(c["q"] == "" for c in svc.calls), (
        "the fallback must NOT re-run the provider query that just missed"
    )


def test_gmail_explicit_ingest_still_queries_provider_first(monkeypatch):
    """The explicit intent=ingest path (no prior search) keeps rung 1 — the
    provider's AND-semantics search — before the newest-N rung."""
    import integrations.gmail_service as gs

    class _QueryingGmail(_FakeGmailService):
        def get_messages(self, query="", max_results=50, **kw):
            self.calls.append({"q": query, "max": max_results})
            if query == "seguin quote":
                return [{"id": "gmail-by-search", "subject": "FW: RFQ",
                         "snippet": "quote", "sender": "joel@example.com"}]
            return []

    monkeypatch.setattr(gs, "GmailService", _QueryingGmail)

    ids = asyncio.run(
        ctp._resolve_mailbox_message_ids("gmail", "u-1", "seguin quote")
    )
    assert ids == ["gmail-by-search"]


def test_gmail_rung_4_requires_two_terms_or_a_figure(monkeypatch):
    """Shared matcher discipline: one common word must not match unrelated
    mail (tightened live 2026-09-12 for outlook; gmail inherits it)."""
    import integrations.gmail_service as gs

    monkeypatch.setattr(gs, "GmailService", _FakeGmailService)

    ids = asyncio.run(
        ctp._resolve_mailbox_message_ids(
            "gmail", "u-1", "invoice", skip_provider_query=True)
    )
    assert ids == []
