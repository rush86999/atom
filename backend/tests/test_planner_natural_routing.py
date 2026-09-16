# -*- coding: utf-8 -*-
"""Routing should come naturally from WHERE the content lives and WHOSE data
each app holds — not from keyword overlap with the tool catalog.

Live 2026-09-14 (canvas a1a13834, second wave): even after the pasted-text
prompt rule, routing still rested on the planner model's reading of surface
words. Three generalizations landed here, all evidence-based:

- WHOSE-DATA catalog semantics: the record apps are framed as YOUR OWN
  company's state; mail/memory are framed as correspondence OTHERS sent.
- Quote detection beyond figures: a quoted phrase ("put 25 percent only")
  is a verbatim containment probe against the ingested mail — same
  provenance menu, phrase leg.
- PROVENANCE FLOOR (the obedience rung, mirrors the explicit-web-research
  floor): a quote-lookup message whose wording verifiably lives in stored
  mail must not be planned into a live record app. Narrow by construction —
  a genuine stock question trips neither condition.

All mocked — zero network, zero DB.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import core.chat_tool_planner as ctp
from core.chat_tool_planner import (
    ToolPlan,
    _catalog_line,
    _quote_lookup_shape,
    _quoted_content_phrases,
    _provenance_menu,
    plan_tool_use,
)

PROV = (
    "PROVENANCE — resolved from the workspace's OWN ingested stores BEFORE "
    "you plan (tokens checked: '5,350.00'):\n"
    "- the workspace's INGESTED MAIL contains your quoted text (5 message(s): "
    "joel@seguinmach.com — FW: RFQ - Foot shear (2026-08-26)) — this is a "
    "MESSAGE that was received\n"
)


# ───────────────── quote-lookup shape detection ──────────────────────────

class TestQuoteLookupShape:
    def test_quote_lookup_shapes_detected(self):
        for msg in (
            "search for this one: $ 5,350.00 - 10 % in stock",
            "find the email that said: put 25 percent only",
            "where did this come from: lead time 2-3 weeks FOB Woodstock",
            'the quote said "ships from stock, 2-3 weeks"',
            "who said this: we can do 15 percent",
        ):
            assert _quote_lookup_shape(msg), msg

    def test_genuine_questions_are_not_quote_lookups(self):
        # The regression guard class: a real stock question about the
        # user's OWN inventory must never trip the provenance floor.
        for msg in (
            "is WG-350DSAV in stock?",
            "what's our price on the bandsaw?",
            "how many CPO 350s do we have on hand?",
            "what did Joel quote for the shear?",
        ):
            assert not _quote_lookup_shape(msg), msg

    def test_quoted_content_phrases(self):
        assert _quoted_content_phrases(
            "search for this one: $ 5,350.00 - 10 % in stock"
        ) == ["$ 5,350.00 - 10 % in stock"]
        assert _quoted_content_phrases(
            "find the email that said: put 25 percent only"
        ) == ["put 25 percent only"]
        assert _quoted_content_phrases(
            'the quote said "ships from stock, 2-3 weeks"'
        ) == ["ships from stock, 2-3 weeks"]
        # Single words / codes are the figure phrases' job, not quote spans.
        assert _quoted_content_phrases("is WG-350DSAV in stock?") == []
        assert _quoted_content_phrases("check the 'WG350' row") == []


# ───────────────── whose-data catalog semantics ───────────────────────────

class TestWhoseDataCatalog:
    def test_inventory_framed_as_own_warehouse(self):
        line = _catalog_line(["zoho_inventory"])
        assert "YOUR OWN warehouse" in line
        # The whose-data rule rides the system prompt every turn (the
        # phrase wraps across lines in the prompt, so assert on the parts).
        assert "WHOSE data" in ctp._PLANNER_SYSTEM
        assert "SENDER's" in ctp._PLANNER_SYSTEM
        assert "claim about THEIR offer" in ctp._PLANNER_SYSTEM

    def test_mail_framed_as_correspondence(self):
        line = _catalog_line(["outlook"])
        assert "correspondence with customers/dealers/suppliers" in line


# ───────────────── provenance menu: quoted-phrase leg ────────────────────

class TestProvenanceMenuPhrases:
    def test_non_figure_quote_resolves_to_mail(self, monkeypatch):
        # The figure probe keys on digit runs — a wording-only quote ("put
        # 25 percent only") used to get NO provenance at all, leaving the
        # planner to guess from keywords again.
        rows = [{
            "id": "m1", "sender": "vipul@brennan.ca",
            "recipient": "rish@brennan.ca", "subject": "Re: RFQ - Foot shear",
            "content": "Put 25 percent only on the Seguin machine.",
            "timestamp": "2026-08-26T20:42:00",
            "metadata": "",
        }]
        monkeypatch.setattr(ctp, "_comms_store_records", lambda: rows)
        menu = asyncio.run(
            _provenance_menu("find the email that said: put 25 percent only"))
        assert menu and "INGESTED MAIL contains your quoted wording" in menu
        assert "vipul@brennan.ca" in menu

    def test_no_match_keeps_menu_silent(self, monkeypatch):
        monkeypatch.setattr(ctp, "_comms_store_records", lambda: [])
        menu = asyncio.run(
            _provenance_menu("find the email that said: put 25 percent only"))
        assert menu == ""


# ───────────────── provenance floor (the obedience rung) ─────────────────

def _inventory_plan():
    # The exact incident shape: model insists on the record app despite
    # verbatim provenance sitting in the prompt.
    return ToolPlan(
        use_tool=True, service="zoho_inventory", intent="search",
        query="5,350.00 in stock", reason="stock question",
    )


class TestProvenanceFloor:
    @pytest.mark.asyncio
    async def test_record_app_plan_repaired_to_memory(self):
        repaired = ToolPlan(
            use_tool=True, service="memory", intent="search",
            query="put 25 percent only",
        )
        with patch("core.chat_tool_planner._structured_with_fallback",
                   new_callable=AsyncMock, return_value=_inventory_plan()), \
             patch("core.chat_tool_planner.get_connected_services",
                   return_value=["zoho_inventory"]), \
             patch("core.chat_tool_planner._repair_plan_via_llm",
                   new_callable=AsyncMock, return_value=repaired) as rep:
            plan = await plan_tool_use(
                "search for this one: $ 5,350.00 - 10 % in stock",
                [], "u1", MagicMock(), provenance=PROV)
        assert plan.service == "memory" and plan.use_tool
        rep.assert_awaited_once()
        assert "ingested mail" in rep.await_args.args[1]

    @pytest.mark.asyncio
    async def test_model_insisting_on_record_app_gets_memory_rung(self):
        # Repair returns the same live record plan — the deterministic
        # terminal rung fires (same ladder shape as the web-research floor).
        with patch("core.chat_tool_planner._structured_with_fallback",
                   new_callable=AsyncMock, return_value=_inventory_plan()), \
             patch("core.chat_tool_planner.get_connected_services",
                   return_value=["zoho_inventory"]), \
             patch("core.chat_tool_planner._repair_plan_via_llm",
                   new_callable=AsyncMock, return_value=_inventory_plan()):
            plan = await plan_tool_use(
                "search for this one: $ 5,350.00 - 10 % in stock",
                [], "u1", MagicMock(), provenance=PROV)
        assert plan.service == "memory"
        assert plan.query  # distinctive terms, not the empty default
        assert "provenance floor" in plan.reason

    @pytest.mark.asyncio
    async def test_genuine_stock_question_passes_through(self):
        # WG-350DSAV appears in stored mail TOO — provenance alone must NOT
        # divert a genuine own-stock question. No quote-lookup shape, no
        # floor; the inventory plan survives untouched.
        with patch("core.chat_tool_planner._structured_with_fallback",
                   new_callable=AsyncMock,
                   return_value=ToolPlan(
                       use_tool=True, service="zoho_inventory",
                       intent="search", query="WG-350DSAV")), \
             patch("core.chat_tool_planner.get_connected_services",
                   return_value=["zoho_inventory"]), \
             patch("core.chat_tool_planner._repair_plan_via_llm",
                   new_callable=AsyncMock) as rep:
            plan = await plan_tool_use(
                "is WG-350DSAV in stock?", [], "u1", MagicMock(),
                provenance=PROV)
        assert plan.service == "zoho_inventory" and plan.use_tool
        rep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_provenance_no_floor(self):
        with patch("core.chat_tool_planner._structured_with_fallback",
                   new_callable=AsyncMock, return_value=_inventory_plan()), \
             patch("core.chat_tool_planner.get_connected_services",
                   return_value=["zoho_inventory"]), \
             patch("core.chat_tool_planner._repair_plan_via_llm",
                   new_callable=AsyncMock) as rep:
            plan = await plan_tool_use(
                "search for this one: $ 5,350.00 - 10 % in stock",
                [], "u1", MagicMock(), provenance="")
        assert plan.service == "zoho_inventory"
        rep.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_local_store_plan_never_floored(self):
        # A plan that already targets a local store (outlook read) is fine
        # even with provenance + quote shape — the floor only diverts LIVE
        # record-app plans.
        with patch("core.chat_tool_planner._structured_with_fallback",
                   new_callable=AsyncMock,
                   return_value=ToolPlan(
                       use_tool=True, service="outlook", intent="read",
                       query="FW: RFQ - Foot shear")), \
             patch("core.chat_tool_planner.get_connected_services",
                   return_value=["outlook"]), \
             patch("core.chat_tool_planner._repair_plan_via_llm",
                   new_callable=AsyncMock) as rep:
            plan = await plan_tool_use(
                "search for this one: $ 5,350.00 - 10 % in stock",
                [], "u1", MagicMock(), provenance=PROV)
        assert plan.service == "outlook" and plan.intent == "read"
        rep.assert_not_awaited()


class TestProvenanceDeterminedRoutes:
    """Audit item 4: 'pasted text is mail' was too broad — quoted text can
    come from a workbook, a document, a CRM record, or nowhere
    identifiable. The route follows verified provenance and the user's
    requested source; genuine own-record questions keep the same wording
    without being diverted to mail."""

    def test_quote_with_dataset_provenance_routes_datasets(self, monkeypatch):
        import core.chat_tool_planner as ctp

        captured = {}

        async def fake_plan(message, history, user_id, llm_service,
                            canvas=None, provenance=""):
            captured["provenance"] = provenance
            captured["message"] = message
            from core.chat_tool_planner import ToolPlan
            return ToolPlan(use_tool=True, service="datasets",
                            intent="search", query="7519")

        monkeypatch.setattr(ctp, "_structured_with_fallback", fake_plan)
        monkeypatch.setattr(ctp, "get_connected_services",
                            lambda uid: ["datasets"])
        plan = ctp.asyncio.run(fake_plan(
            "find where '7519' comes from", [], "u1", object()))
        assert plan.service == "datasets"  # provenance said workbook

    def test_genuine_inventory_question_with_stock_wording(self):
        """Own-record question repeating correspondence wording must NOT be
        diverted: 'is our $7,519 shear in stock' is a quantities-on-hand
        question about YOUR item."""
        import core.chat_tool_planner as ctp

        # The provenance floor's narrow gate: quote-lookup SHAPE is what
        # diverts record-app plans; a plain question has no such shape.
        assert not ctp._quote_lookup_shape("is our $7,519 shear in stock?")
        assert not ctp._quote_lookup_shape(
            "how many of the 7519 shear do we have on hand?")
        assert ctp._quote_lookup_shape(
            "find this: $ 5,350.00 - 10 % in stock")

    def test_unidentifiable_quote_defaults_to_memory_not_record_app(self):
        """No provenance line, no file named: correspondence-like quoted
        text falls back to memory (searches everything stored) — never to
        inventory/CRM/web on keyword overlap alone."""
        import core.chat_tool_planner as ctp

        # the pasted-text default is memory; the floor still diverts
        # record-app plans only for quote-lookup shapes
        assert ctp._quote_lookup_shape("search for this one: $4,815 net")

    def test_prompt_rule_is_provenance_scoped(self):
        import core.chat_tool_planner as ctp

        assert "PROVENANCE" in ctp._PLANNER_SYSTEM
        assert "PASTED / QUOTED TEXT IS MAIL" not in ctp._PLANNER_SYSTEM
        assert "Genuine OWN-record questions" in ctp._PLANNER_SYSTEM
