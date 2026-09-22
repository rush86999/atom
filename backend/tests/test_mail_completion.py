# -*- coding: utf-8 -*-
"""ID-targeted mailbox completion: structured handles, validated reads,
durable persistence, topic isolation — and the decisive two-turn regression.

The acceptance shape (2026-09-22 incident follow-through): a search returns
named products plus unresolved message ids → the assistant offers to read the
rest → the user approves ("yes go ahead") → the planner receives those exact
ids → the reads complete → THE ANSWER identifies the remaining products.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import integrations.chat_orchestrator as chat
import core.chat_tool_planner as planner
from core.chat_tool_planner import (
    ToolPlan,
    _extract_mail_ids,
    _outlook_read_by_ids,
    _validate_mail_ids,
)

ID1 = "A" * 60
ID2 = "B" * 59 + "=1"   # '=' padding must survive extraction
ID_OTHER = "C" * 60

PRODUCT_1 = "Yanmar laser YL-500 asking CAD 42,000"
PRODUCT_2 = "Amada shear 355 asking CAD 18,900"


def _ids_block(text_by_id):
    lines = []
    for eid, text in text_by_id.items():
        lines.append(f"- READ OK (FULL BODY) | message_id: {eid}\n{text}")
    return (
        "LIVE TOOL RESULTS (outlook.read_emails, query='message_id: …') — "
        "direct reads: %d/%d retrieved; use the bodies to answer:\n" % (
            len(text_by_id), len(text_by_id))
        + "\n".join(lines)
    )


class TestExtractMailIds:
    def test_equals_padding_survives(self):
        q = f"read message_id: {ID2} in full"
        assert _extract_mail_ids(q) == [ID2]

    def test_multiple_ids_deduped_in_order(self):
        q = f"message_id: {ID1} and message_id: {ID2} and message_id: {ID1}"
        assert _extract_mail_ids(q) == [ID1, ID2]

    def test_trailing_punctuation_stripped(self):
        q = f"message_id: {ID1}."
        assert _extract_mail_ids(q) == [ID1]

    def test_prose_yields_nothing(self):
        assert _extract_mail_ids("open that machinery email again") == []


class TestValidation:
    def test_handle_allow_list(self):
        allowed, rejected = _validate_mail_ids(
            [ID1, ID_OTHER], {"known_mail_handles": [{"id": ID1}],
                              "message": "yes go ahead"})
        assert allowed == [ID1]
        assert ID_OTHER in rejected

    def test_user_pasted_id_is_authorized(self):
        allowed, rejected = _validate_mail_ids(
            [ID2], {"known_mail_handles": [], "message": f"read {ID2} please"})
        assert allowed == [ID2]
        assert not rejected

    def test_bare_harness_keeps_legacy_accept(self):
        # No message and no handles in context → not the chat lane; legacy
        # behaviour (dedicated validation tests cover the enforced path).
        allowed, rejected = _validate_mail_ids([ID1], {})
        assert allowed == [ID1] and not rejected

    async def _noop(self):
        pass


class TestReadByIds:
    def test_rejected_ids_cost_zero_provider_calls(self):
        calls = []

        async def fake_get(user_id, email_id, token=None):
            calls.append(email_id)
            return None

        from integrations import outlook_service as osvc_mod
        with patch.object(osvc_mod.outlook_service, "get_email_by_id",
                          side_effect=fake_get):
            outcomes = asyncio.run(_outlook_read_by_ids(
                "u1", [ID_OTHER], 20000,
                context={"message": "yes go ahead",
                         "known_mail_handles": [{"id": ID1}]}))
        assert outcomes[ID_OTHER]["outcome"] == "rejected"
        assert calls == [], "a rejected id must never reach the provider"

    def test_multi_id_full_reads_with_per_id_outcomes(self):
        from integrations import outlook_service as osvc_mod

        async def fake_get(user_id, email_id, token=None):
            return {"id": email_id, "body": {"contentType": "text",
                                             "content": "body of " + email_id}}

        with patch.object(osvc_mod.outlook_service, "get_email_by_id",
                          side_effect=fake_get):
            outcomes = asyncio.run(_outlook_read_by_ids(
                "u1", [ID1, ID2], 20000, context={} ))
        assert outcomes[ID1]["outcome"] == "full"
        assert outcomes[ID2]["outcome"] == "full"
        assert "body of " + ID2 in outcomes[ID2]["text"]

    def test_timeout_vs_not_attempted_are_distinguished(self):
        from integrations import outlook_service as osvc_mod

        async def fake_get(user_id, email_id, token=None):
            if email_id == ID1:
                await asyncio.sleep(30)  # started, never finishes
            return {"id": email_id, "body": {"contentType": "text",
                                             "content": "quick body"}}

        # budget_seconds=0.5 → wave timeout ~0.5s; 8 ids → wave 2 never runs.
        # Wave 1 = [ID1(slow), D0..D4]; wave 2 = [D5, ID2] is unscheduled.
        wave1_fast = ["D" * 60 + str(n) for n in range(5)]
        with patch.object(osvc_mod.outlook_service, "get_email_by_id",
                          side_effect=fake_get):
            outcomes = asyncio.run(_outlook_read_by_ids(
                "u1", [ID1] + wave1_fast + ["D" * 60 + "5", ID2],
                20000, budget_seconds=0.5, context={}))
        for eid in wave1_fast:
            assert outcomes[eid]["outcome"] == "full", eid
        assert outcomes[ID1]["outcome"] == "timed_out"
        assert outcomes["D" * 60 + "5"]["outcome"] == "not_attempted"
        assert outcomes[ID2]["outcome"] == "not_attempted"


class TestSearchPathHandles:
    def test_preview_lines_carry_ids_and_meta_lists_unread(self):
        def _hit(eid, subject):
            return {"id": eid, "subject": subject,
                    "body_preview": "cut…",
                    "from_field": {"emailAddress": {"address": "s@x.com"}},
                    "received_date_time": "2026-09-08T10:00:00"}

        hits = [_hit(ID1, "Fw: machinery one"), _hit(ID2, "Fw: machinery two"),
                _hit("E" * 60, "Fw: machinery three")]

        from integrations import outlook_service as osvc_mod

        async def fake_search(user_id, query, max_results=50, token=None, quote=True):
            return [dict(h) for h in hits]

        async def fake_get(user_id, email_id, token=None):
            if email_id == ID1:
                return {"id": email_id, "body": {"contentType": "text",
                                                 "content": PRODUCT_1}}
            return None

        plan = ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="machinery", reason="t")
        with patch.object(osvc_mod.outlook_service, "search_emails",
                          side_effect=fake_search), \
             patch.object(osvc_mod.outlook_service, "get_email_by_id",
                          side_effect=fake_get), \
             patch.object(planner, "_ingested_mailbox_lines",
                          side_effect=lambda *a, **k: []), \
             patch.object(planner, "_memory_search_block",
                          side_effect=lambda *a, **k: None), \
             patch.object(planner, "_latest_styled_ingested",
                          side_effect=lambda *a, **k: None):
            block = asyncio.run(execute_tool_plan if False else planner.execute_tool_plan(
                plan, "u1", "default", context={"message": "machinery list"}))
        assert "FULL BODY:" in block and PRODUCT_1 in block
        # Preview lines carry the EXACT id (including '=' padding).
        assert f"message_id: {ID2}" in block
        # Honest completion state, not a blanket hint.
        assert "NOT read in full" in block
        assert "Do NOT claim you reviewed every message" in block
        # Structured meta — never parsed back from this prose.
        unread = plan._result_meta["unread_mail"]
        assert {h["id"] for h in unread} == {ID2, "E" * 60}
        assert all(h["origin_query"] == "machinery" for h in unread)

    def test_truncated_body_is_marked_excerpt_with_verified_remedy(self):
        def _hit(eid, subject):
            return {"id": eid, "subject": subject,
                    "body_preview": "cut…",
                    "from_field": {"emailAddress": {"address": "s@x.com"}},
                    "received_date_time": "2026-09-08T10:00:00"}

        hits = [_hit(ID1, "Fw: machinery")]
        long_body = PRODUCT_1 + " filler " * 4000 + " tail content"

        from integrations import outlook_service as osvc_mod

        async def fake_search(user_id, query, max_results=50, token=None, quote=True):
            return [dict(h) for h in hits]

        async def fake_get(user_id, email_id, token=None):
            return {"id": email_id, "body": {"contentType": "text",
                                             "content": long_body}}

        plan = ToolPlan(use_tool=True, service="outlook", intent="search",
                        query="machinery", reason="t")
        with patch.object(osvc_mod.outlook_service, "search_emails",
                          side_effect=fake_search), \
             patch.object(osvc_mod.outlook_service, "get_email_by_id",
                          side_effect=fake_get), \
             patch.object(planner, "_ingested_mailbox_lines",
                          side_effect=lambda *a, **k: []), \
             patch.object(planner, "_memory_search_block",
                          side_effect=lambda *a, **k: None), \
             patch.object(planner, "_latest_styled_ingested",
                          side_effect=lambda *a, **k: None):
            block = asyncio.run(planner.execute_tool_plan(
                plan, "u1", "default", context={"message": "machinery"}))
        assert "EXCERPT — middle elided" in block
        assert "documents.read" in block and "start_line=" in block


# ---------------------------------------------------------------------------
# Handle persistence + topic isolation
# ---------------------------------------------------------------------------

class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows
        self._limit_n = None

    def filter(self, *a):
        return self

    def order_by(self, *a):
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    def all(self):
        return list(self._rows[:self._limit_n] if self._limit_n else self._rows)


class _FakeDb:
    def __init__(self, rows):
        self._rows = rows
        self.added = []

    def query(self, *a):
        return _FakeQuery(self._rows)

    def add(self, row):
        self.added.append(row)

    def commit(self):
        pass


@contextmanager
def _fake_db_session(rows):
    yield _FakeDb(rows)


def _row(meta, role="assistant", content="reply"):
    return SimpleNamespace(role=role, content=content,
                           metadata_json=json.dumps(meta) if meta else None,
                           created_at="2026-09-22T12:00:00")


class TestHandlePersistence:
    def test_loader_aggregates_pending_minus_read(self):
        orch = chat.ChatOrchestrator()
        rows = [
            _row({"mail_handles": {
                "unread_mail": [{"id": ID1, "subject": "s1",
                                 "origin_request": "machinery list"}],
                "read_outcomes": []}}),
            _row({"mail_handles": {
                "unread_mail": [{"id": ID2, "subject": "s2",
                                 "origin_request": "machinery list"}],
                "read_outcomes": [{"id": ID2, "outcome": "full"}]}}),
        ]
        with patch("core.database.get_db_session", lambda: _fake_db_session(rows)):
            handles = orch._load_conversation_mail_handles("sess-1")
        # ID2 was read IN FULL → leaves pending; ID1 stays.
        assert [h["id"] for h in handles] == [ID1]

    def test_excerpt_outcome_stays_pending(self):
        orch = chat.ChatOrchestrator()
        rows = [
            _row({"mail_handles": {
                "unread_mail": [{"id": ID1, "subject": "s1",
                                 "origin_request": "machinery"}],
                "read_outcomes": [{"id": ID1, "outcome": "excerpt"}]}}),
        ]
        with patch("core.database.get_db_session", lambda: _fake_db_session(rows)):
            handles = orch._load_conversation_mail_handles("sess-1")
        assert [h["id"] for h in handles] == [ID1]

    def test_update_session_persists_handles_into_metadata(self):
        orch = chat.ChatOrchestrator()
        session = {"id": "sess-1", "history": [],
                   "_pending_mail_meta": {
                       "unread_mail": [{"id": ID1, "subject": "s",
                                        "origin_request": "machinery",
                                        "origin_query": "machinery"}],
                       "read_outcomes": []}}
        db = _FakeDb([])
        with patch("core.database.get_db_session", lambda: _fake_ctx(db)):
            orch._update_session(session, "machinery list",
                                 {"message": "found hits", "success": True}, {})
        assistant_rows = [r for r in db.added if getattr(r, "role", "") == "assistant"]
        assert assistant_rows, "assistant row must be persisted"
        meta = json.loads(assistant_rows[0].metadata_json)
        assert meta["mail_handles"]["unread_mail"][0]["id"] == ID1
        assert "_pending_mail_meta" not in session


@contextmanager
def _fake_ctx(db):
    yield db


class TestTopicIsolation:
    HANDLES = [
        {"id": ID1, "subject": "Fw: machinery list",
         "origin_request": "Steve Macisaac machinery requested",
         "origin_query": "Steve Macisaac machinery"},
        {"id": ID2, "subject": "Fw: machinery quote (other lead)",
         "origin_request": "check the other machinery quote",
         "origin_query": "other machinery quote"},
    ]

    def test_lineage_identity_selects_only_the_matching_lead(self):
        orch = chat.ChatOrchestrator()
        from core.plan_relevance import resolve_request_reference

        ref = resolve_request_reference("yes go ahead", [
            {"message": "Steve Macisaac machinery requested",
             "response": {"message": "Want me to pull the full list?"}}])
        out = orch._advertise_mail_handles(self.HANDLES, "yes go ahead", ref)
        # Both origins contain the word "machinery" — keyword overlap must
        # NOT advertise the second lead; lineage IDENTITY picks the first.
        assert [h["id"] for h in out] == [ID1]

    def test_explicit_target_identity_advertises_for_direct_turns(self):
        orch = chat.ChatOrchestrator()
        from core.plan_relevance import _direct_reference

        ref = _direct_reference(f"read {ID2} in full")
        out = orch._advertise_mail_handles(self.HANDLES, f"read {ID2} in full", ref)
        assert [h["id"] for h in out] == [ID2]


class TestPendingHandlesBlock:
    def test_renders_id_directed_instruction(self):
        from core.session_sources import pending_mail_handles_block

        block = pending_mail_handles_block(
            [{"id": ID1, "subject": "Fw: machinery", "origin_query": "q"}])
        assert "message_id: " + ID1 in block
        assert "NOT YET READ IN FULL" in block
        assert "never cite their contents" in block

    def test_empty_handles_render_nothing(self):
        from core.session_sources import pending_mail_handles_block

        assert pending_mail_handles_block([]) == ""


# ---------------------------------------------------------------------------
# THE DECISIVE TWO-TURN REGRESSION
# ---------------------------------------------------------------------------

def _hit(eid, subject):
    return {"id": eid, "subject": subject, "body_preview": "cut…",
            "from_field": {"emailAddress": {"address": "s@x.com"}},
            "received_date_time": "2026-09-08T10:00:00"}


@pytest.mark.asyncio
async def test_approval_turn_reads_unresolved_ids_and_answer_names_products():
    """Search → offer → 'yes go ahead' → planner gets the EXACT ids → reads
    complete → the ANSWER identifies the remaining products."""
    orch = chat.ChatOrchestrator()
    session = {"id": "sess-2t", "history": [
        {"message": "Steve Macisaac machinery requested",
         "response": {"message": "I found 3 mailbox hits. I read one in "
                                 "full; two remain preview-only — want me "
                                 "to read the rest and identify the "
                                 "machines?"}},
    ]}
    planned_kwargs = {}
    executed_contexts = []

    async def fake_plan(message, hist, user_id, llm, canvas=None, provenance=""):
        planned_kwargs["provenance"] = provenance
        return ToolPlan(use_tool=True, service="outlook", intent="read",
                        query=f"message_id: {ID1} message_id: {ID2}",
                        reason="complete the machinery list")

    async def fake_execute(plan, user_id, tenant_id, context=None,
                           llm_service=None):
        executed_contexts.append(context)
        outcomes = [{"id": ID1, "outcome": "full"},
                    {"id": ID2, "outcome": "full"}]
        plan._result_meta["read_outcomes"] = outcomes
        return _ids_block({ID1: PRODUCT_1, ID2: PRODUCT_2})

    def _answer(**kwargs):
        messages = kwargs.get("messages") or []
        text = " ".join(str(m.get("content") or "") for m in messages)
        found = [p for p in (PRODUCT_1, PRODUCT_2) if p in text]
        assert found, "the evidence must reach the reply prompt in full"
        return {"success": True, "content": "The remaining machines are: "
                                             + "; ".join(found),
                "model": "m", "provider": "p"}

    llm = MagicMock()
    llm.generate_completion = AsyncMock(side_effect=_answer)

    handles = [{"id": ID1, "subject": "Fw: machinery one",
                "origin_request": "Steve Macisaac machinery requested",
                "origin_query": "Steve Macisaac machinery"},
               {"id": ID2, "subject": "Fw: machinery two",
                "origin_request": "Steve Macisaac machinery requested",
                "origin_query": "Steve Macisaac machinery"}]

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_load_conversation_mail_handles", return_value=handles),
        patch.object(chat.planner if False else planner, "_provenance_menu",
                     new=AsyncMock(return_value="")),
        patch.object(planner, "plan_tool_use", side_effect=fake_plan),
        patch.object(planner, "execute_tool_plan", side_effect=fake_execute),
    ):
        orch.llm_service = llm
        result = await orch.process_chat_message(
            "u1", "yes go ahead", "sess-2t", context={})

    # (1) The planner received the EXACT unresolved ids via the sources block.
    prov = planned_kwargs["provenance"]
    assert f"message_id: {ID1}" in prov
    assert f"message_id: {ID2}" in prov
    # (2) The executor read exactly those ids, authorized via handles.
    assert executed_contexts, "executor must run on the approval turn"
    known = {str(h.get("id") if isinstance(h, dict) else h)
             for h in executed_contexts[0].get("known_mail_handles") or []}
    assert {ID1, ID2} <= known
    # (3) THE ANSWER identifies the remaining products — the acceptance
    # criterion, not just successful reads.
    assert PRODUCT_1 in result["message"]
    assert PRODUCT_2 in result["message"]


@pytest.mark.asyncio
async def test_unresolved_approval_clarifies_without_scheduling_a_lookup():
    """Structural clarify guarantee: no plan task is created, so no lookup
    can run behind an approval whose referent cannot be pinned."""
    orch = chat.ChatOrchestrator()
    session = {"id": "sess-cl", "history": []}
    captured = {}

    async def fail_plan(*a, **k):
        raise AssertionError("plan_tool_use must not run on a clarify turn")

    async def fake_reply(message, history, routing_overrides=None, **kwargs):
        captured["reference"] = kwargs.get("request_reference")
        return {"content": "Which item would you like?", "model": "m",
                "provider": "p"}

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx", new=AsyncMock(return_value=None)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(planner, "plan_tool_use", side_effect=fail_plan),
        patch.object(orch, "_get_qwen_response", side_effect=fake_reply),
    ):
        result = await orch.process_chat_message(
            "u1", "yes go ahead", "sess-cl", context={})
    ref = captured["reference"]
    assert ref is not None and ref.kind == "unresolved"
    assert result["message"] == "Which item would you like?"


from core.chat_tool_planner import execute_tool_plan  # noqa: E402  (used above)
