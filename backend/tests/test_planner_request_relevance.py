# -*- coding: utf-8 -*-
"""The plan must answer the CURRENT request, not an older one.

RCA 2026-09-17 finding 2 (canvas a1a13834): the final turn asked for a
vendor scorecard's reliability 0.87, and the executed plan was
``outlook.search 'PRICE VIPUL price list attachment'`` — an earlier ask.
Three layers land here:

* prompt-side (`_history_transcript`): earlier asks are labelled CONTEXT and
  the last message is labelled CURRENT REQUEST, so the planning model is
  told which ask to plan for;
* in-planner replan arm (`plan_tool_use` relevance floor): a plan whose
  query names nothing the current message names gets ONE corrective pass
  re-targeted at the current request — upstream of the consumption-side
  off-request gates, which decline what this arm cannot repair;
* detector (core.plan_relevance, the concurrent session's module): the
  incident's exact pair must classify as irrelevant, and rewrites that keep
  an identifier must stay relevant.

The replan arm's latency contract: it fires ONLY where the consumption gate
would have discarded the execution anyway, so a repair costs nothing on
healthy turns.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock

from core.chat_tool_planner import ToolPlan, _history_transcript, plan_tool_use

SCORECARD_ASK = (
    "search for this one: reliability score 0.87 from the vendor scorecard "
    "workbook"
)

HISTORY = [
    {"message": "search for this one: $ 5,350.00 - 10 % in stock",
     "response": {"message": "Found the Seguin email quoting $5,350.00 - 10%."}},
    {"message": (
        "which emails did we send that carried the PRICE VIPUL price list "
        "as an attachment?"),
     "response": {"message": "Only the internal Chandrakant forward."}},
    {"message": "open PRICE VIPUL and show how the 7519 listed price was derived",
     "response": {"message": "PRICE VIPUL (6).xlsx — Sheet1 — row 235: N235 = ROUNDUP(M235,0) = 7519.0"}},
]


def _llm(*plans):
    llm = SimpleNamespace()
    llm.generate_structured_response = AsyncMock(side_effect=list(plans))
    return llm


def _planner_env(monkeypatch, connected=("outlook", "datasets")):
    monkeypatch.setattr("core.chat_tool_planner.get_connected_services",
                        lambda user_id: list(connected))
    monkeypatch.setattr("core.chat_tool_planner._available_platform_services",
                        lambda: [])


class TestTranscriptLabels:
    def test_current_request_is_marked(self):
        out = _history_transcript(HISTORY, SCORECARD_ASK)
        assert "CURRENT REQUEST (plan for THIS message):" in out
        assert out.rstrip().endswith("vendor scorecard workbook")

    def test_earlier_asks_are_labelled_context_with_retry_carveout(self):
        out = _history_transcript(HISTORY, SCORECARD_ASK)
        assert "Earlier requests (CONTEXT only" in out
        assert "unless the current message explicitly asks to retry one" in out
        # every earlier ask is still visible (anaphora/retries resolve there)
        assert "PRICE VIPUL price list" in out

    def test_empty_history_still_marks_the_current_request(self):
        out = _history_transcript([], SCORECARD_ASK)
        assert "CURRENT REQUEST" in out
        assert "Earlier requests" not in out


class TestIncidentVerdict:
    def test_the_incident_plan_is_irrelevant(self):
        from core.plan_relevance import relevance_verdict
        assert relevance_verdict(
            "PRICE VIPUL price list attachment", SCORECARD_ASK) == "irrelevant"

    def test_a_rewrite_that_keeps_an_identifier_is_relevant(self):
        from core.plan_relevance import relevance_verdict
        assert relevance_verdict(
            "vendor scorecard 0.87", SCORECARD_ASK) == "relevant"

    def test_an_empty_query_fails_open(self):
        from core.plan_relevance import relevance_verdict
        assert relevance_verdict("", SCORECARD_ASK) == "unknown"


class TestReplanArm:
    async def test_off_target_plan_is_repaired_to_current_request(
            self, monkeypatch):
        _planner_env(monkeypatch)
        off = ToolPlan(use_tool=True, service="outlook", intent="search",
                       query="PRICE VIPUL price list attachment")
        on = ToolPlan(use_tool=True, service="datasets", intent="search",
                      query="vendor scorecard reliability 0.87")
        plan = await plan_tool_use(SCORECARD_ASK, HISTORY, "u1", _llm(off, on))
        assert plan.service == "datasets"
        assert "0.87" in plan.query

    async def test_a_healthy_plan_never_pays_a_second_call(self, monkeypatch):
        _planner_env(monkeypatch)
        on = ToolPlan(use_tool=True, service="datasets", intent="search",
                      query="vendor scorecard reliability 0.87")
        llm = _llm(on)  # a second structured call would raise StopIteration
        plan = await plan_tool_use(SCORECARD_ASK, HISTORY, "u1", llm)
        assert "0.87" in plan.query
        assert llm.generate_structured_response.await_count == 1

    async def test_unrepairable_plan_is_kept_for_the_consumption_gate(
            self, monkeypatch):
        """Repair still off-target: the ORIGINAL plan is returned unchanged
        and the consumption-side off-request gate declines its execution —
        the planner never makes the turn worse than declining would."""
        _planner_env(monkeypatch)
        off = ToolPlan(use_tool=True, service="outlook", intent="search",
                       query="PRICE VIPUL price list attachment")
        still_off = ToolPlan(use_tool=True, service="outlook",
                             intent="search",
                             query="RFQ technical criteria PDFs")
        plan = await plan_tool_use(SCORECARD_ASK, HISTORY, "u1",
                                   _llm(off, still_off))
        assert plan.service == "outlook"
        assert plan.query == "PRICE VIPUL price list attachment"

    async def test_repair_declining_tool_use_is_honored(self, monkeypatch):
        _planner_env(monkeypatch)
        off = ToolPlan(use_tool=True, service="outlook", intent="search",
                       query="PRICE VIPUL price list attachment")
        decline = ToolPlan(use_tool=False, service=None, intent="search")
        plan = await plan_tool_use(SCORECARD_ASK, HISTORY, "u1",
                                   _llm(off, decline))
        assert plan is None

    async def test_canvas_target_stamp_requires_edit_opt_in(self, monkeypatch):
        _planner_env(monkeypatch)
        canvas = {
            "canvas_id": "cv-quote",
            "title": "Quote - Roper Whitney Roll Bender, Linmac Bead Roller, Slitters",
            "content": {"body": "<table><tr><td>Roper Whitney No. 381</td></tr></table>"},
        }
        source = ToolPlan(
            use_tool=True, service="outlook", intent="search",
            query="Chandrakant amacisaac alternatives roll bender bead roller flanger slitter",
        )
        plan = await plan_tool_use(
            "update with actual prices in the email", [], "u1", _llm(source),
            canvas=canvas, allow_canvas_target=True,
        )
        assert plan.relevance_verdict == "relevant"
        assert plan.relevance_basis == "canvas-target"

    async def test_canvas_target_is_not_used_by_an_ordinary_canvas_turn(
            self, monkeypatch):
        _planner_env(monkeypatch)
        canvas = {
            "canvas_id": "cv-quote",
            "title": "Quote - Roper Whitney Roll Bender",
            "content": {"body": "<table><tr><td>Roper Whitney</td></tr></table>"},
        }
        source = ToolPlan(
            use_tool=True, service="outlook", intent="search",
            query="roll bender alternatives",
        )
        plan = await plan_tool_use(
            "check the vendor scorecard", [], "u1", _llm(source),
            canvas=canvas,
        )
        assert plan.relevance_verdict != "relevant"

    async def test_anaphoric_retry_is_never_gated(self, monkeypatch):
        """'try again' carries no identifiers — the relevance verdict is
        'unknown' and the retry keeps its single-call contract."""
        _planner_env(monkeypatch)
        retry = ToolPlan(use_tool=True, service="outlook", intent="search",
                         query="PRICE VIPUL price list attachment")
        llm = _llm(retry)
        plan = await plan_tool_use("try again", HISTORY, "u1", llm)
        assert plan.service == "outlook"
        assert llm.generate_structured_response.await_count == 1
