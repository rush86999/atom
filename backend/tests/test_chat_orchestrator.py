import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from integrations.chat_orchestrator import ChatOrchestrator, ChatIntent, FeatureType

@pytest.mark.asyncio
class TestChatOrchestrator:

    async def _no_ai_response(self, orchestrator):
        # Current flow: when the LLM returns nothing usable, the orchestrator
        # falls back to the template/main-message path (feature responses).
        orchestrator._get_qwen_response = AsyncMock(return_value=None)

    async def test_fallback_to_agent_service(self):
        """Test that unhandled requests fallback to ComputerUseAgent"""
        orchestrator = ChatOrchestrator()
        
        # Mock dependencies
        orchestrator.ai_engines = {} # Disable AI engines to force fallback analysis
        await self._no_ai_response(orchestrator)
        
        # Helper to bypass _analyze_intent natural language processing.
        # NOTE (R82): agent dispatch is intentionally scoped to explicit
        # AGENT_REQUEST intents — SEARCH_REQUEST no longer falls back to
        # ComputerUseAgent (the feature handlers own that intent; the pre-2026
        # blanket fallback was removed to avoid recursive agent spend).
        orchestrator._analyze_intent = AsyncMock(return_value={
            "primary_intent": ChatIntent.AGENT_REQUEST,
            "confidence": 0.5,
            "entities": [],
            "platforms": [],
            "command_type": "agent_request"
        })
        
        # Mock feature handlers to fail or return nothing, triggering fallback
        # Important: SEARCH_REQUEST maps to [SEARCH, AI_ANALYTICS]. Both must fail/be missing.
        # We replace the entire feature_handlers dict to be sure.
        orchestrator.feature_handlers = {
            FeatureType.SEARCH: AsyncMock(return_value={"success": False}),
            FeatureType.AI_ANALYTICS: AsyncMock(return_value={"success": False})
        }
        
        # Mock agent_service
        # Patch the class method to ensure it catches all instances
        with patch("services.agent_service.ComputerUseAgent.execute_task", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"id": "task_123", "status": "running"}
            
            response = await orchestrator.process_chat_message("test_user", "Research quantum physics")
            
            # Should have called execute_task
            print(f"Mock called? {mock_execute.called}")
            print(f"Mock call count: {mock_execute.call_count}")
            print(f"Mock calls: {mock_execute.mock_calls}")
            
            mock_execute.assert_called_once()
            assert response["success"] is True
            assert "task_123" in response["message"]  # R82: message copy now "Task initiated. ID: <id>"
            
    async def test_explicit_agent_request(self):
        """Test explicit agent request routing"""
        orchestrator = ChatOrchestrator()
        await self._no_ai_response(orchestrator)
        
        # Mock FeatureType.AGENT handler to avoid DB calls
        orchestrator.feature_handlers[FeatureType.AGENT] = AsyncMock(return_value={"success": False})
        
        orchestrator._analyze_intent = AsyncMock(return_value={
            "primary_intent": ChatIntent.AGENT_REQUEST,
            "confidence": 1.0, 
            "entities": [],
            "platforms": [],
            "command_type": "agent"
        })
        
        with patch("services.agent_service.ComputerUseAgent.execute_task", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"id": "task_456", "status": "running"}
            
            response = await orchestrator.process_chat_message("test_user", "Please research this")
            
            mock_execute.assert_called_once()
            assert response["success"] is True


# --------------------------------------------------------------------------- #
# planner TIMEOUT → deterministic evidence (or an honest "nothing ran" note)
# --------------------------------------------------------------------------- #

def test_planner_timeout_injects_deterministic_mailbox_evidence(monkeypatch):
    """Live 2026-09-13: the overlapped canvas-edit plan took 31-38s, the 25s
    planner wait expired with NO plan, no evidence block was injected, and the
    reply invented a Zoho Inventory lookup it never ran. The timeout path must
    hand the model real ingested-mail evidence instead of a vacuum."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _planner_timeout_evidence

    async def fake_lines(user_id, query, context=None, **kw):
        return ["- [ingested mailbox] From: joel@seguinmach.example | quote | $ 5,350.00"]

    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", fake_lines)

    block = asyncio.run(
        _planner_timeout_evidence(
            "search for this one: $ 5,350.00", "u1", {"history": []}
        )
    )

    # Re-contracted 2026-09-15: the timeout path is HANDLE-LED first — a
    # message carrying figures/phrases/participants resolves through the
    # verbatim-evidence legs (mail-led, live-failure demoted to the trailing
    # note) BEFORE the generic mailbox scan. Both contracts inject real
    # evidence instead of a vacuum; the handle-led block is the stronger one.
    assert block and "LIVE TOOL RESULTS" in block
    assert "ingested mailbox" in block
    assert "could not complete in time" in block
    assert "GROUNDING RULE" in block, "evidence must carry the grounding contract"


def test_planner_timeout_without_evidence_says_nothing_ran(monkeypatch):
    """No evidence is not a licence to invent: the note must forbid claiming a
    search that never happened."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _planner_timeout_evidence

    async def empty_lines(user_id, query, context=None, **kw):
        return []

    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", empty_lines)

    block = asyncio.run(_planner_timeout_evidence("hello", "u1", {"history": []}))

    assert block
    assert "NO TOOL LOOKUP RAN" in block
    low = block.lower()
    assert "do not describe a search you did not run" in low
    assert "do not name a system you did not query" in low
    assert "never invent tool activity" in low


def test_planner_timeout_fallback_is_fault_isolated(monkeypatch):
    """A broken scan must degrade to the honest note, never raise into the
    turn (the fallback must not become the failure)."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _planner_timeout_evidence

    async def boom(user_id, query, context=None, **kw):
        raise RuntimeError("lance exploded")

    monkeypatch.setattr(ctp, "_ingested_mailbox_lines", boom)

    block = asyncio.run(_planner_timeout_evidence("hello", "u1", {"history": []}))
    assert block == __import__(
        "integrations.chat_orchestrator", fromlist=["_NO_LOOKUP_BLOCK"]
    )._NO_LOOKUP_BLOCK


def test_planner_timeout_fallback_skipped_without_user():
    import asyncio

    from integrations.chat_orchestrator import _planner_timeout_evidence

    assert asyncio.run(_planner_timeout_evidence("hi", None, {})) is None


# --------------------------------------------------------------------------- #
# a PASTED QUOTE must answer from mail even when the planner mis-routes
# --------------------------------------------------------------------------- #

def test_verbatim_mail_evidence_finds_the_quoted_amount(monkeypatch):
    """Live 2026-09-14: 'search for this one: $ 5,350.00 - 10 % in stock' was
    routed to zoho_inventory (the quote contains 'stock'), the lookup timed
    out, and the reply told the user their own quote could not be found. The
    figure scan must run INDEPENDENTLY of the planner's choice."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _verbatim_mail_evidence

    seen = {}

    def fake_tokens(user_id, tokens, limit=4, date_window=None):
        seen["tokens"] = tokens
        return ["- [ingested mailbox] From: joelseguin@seguinmach.com | "
                "FW: RFQ - Foot shear | $ 5,350.00 – 10 % in stock | "
                "full: knowledge/conversations/msg-1"]

    monkeypatch.setattr(ctp, "_search_ingested_by_tokens", fake_tokens)

    lines = asyncio.run(
        _verbatim_mail_evidence(
            "search for this one: $ 5,350.00 - 10 % in stock", "u1",
            {"history": []},
        )
    )

    assert lines and "5,350.00" in lines[0]
    assert seen["tokens"] == ["5,350.00"], seen


def test_verbatim_mail_evidence_skips_queries_without_a_figure(monkeypatch):
    """No handle (figure, quoted phrase, participant+referent) → no store
    walk at all (the common case). Re-contracted 2026-09-14: the evidence
    choke point grips more than figures now — "what did Sarah say about the
    deadline" IS a mail ask and may scan (names resolve against the STORE,
    so an unknown Sarah still returns []). Referent-free person mentions
    ("schedule a call with chandrakant") must NOT scan."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _verbatim_mail_evidence

    def boom(*a, **k):
        raise AssertionError("must not scan for a handle-less message")

    monkeypatch.setattr(ctp, "_search_ingested_by_tokens", boom)
    monkeypatch.setattr(ctp, "_comms_store_records", boom)

    assert asyncio.run(
        _verbatim_mail_evidence("what is the capital of France", "u1", {})
    ) == []
    assert asyncio.run(
        _verbatim_mail_evidence(
            "schedule a call with chandrakant tomorrow", "u1", {})
    ) == []


def test_verbatim_mail_evidence_is_fault_isolated(monkeypatch):
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _verbatim_mail_evidence

    def boom(*a, **k):
        raise RuntimeError("lance exploded")

    monkeypatch.setattr(ctp, "_search_ingested_by_tokens", boom)
    assert asyncio.run(_verbatim_mail_evidence("$ 5,350.00", "u1", {})) == []


def test_live_failure_note_does_not_bury_mail_evidence():
    """The demoted failure wording must not read as 'your item could not be
    found' — that inversion is exactly what the user saw."""
    from integrations.chat_orchestrator import _LIVE_LOOKUP_FAILED_NOTE

    note = _LIVE_LOOKUP_FAILED_NOTE.format(service="zoho_inventory")
    assert "does NOT affect the mailbox evidence" in note
    assert "answer the question from it now" in note
    # Re-contracted 2026-09-16: the note now LEADS-FORCES the answer and
    # caps the failure at one closing sentence.
    assert "Do NOT open your reply with the failed lookup" in note
    assert "never as the reason the item could not be found" in note


def test_planner_prompt_forbids_pasted_quotes_going_to_inventory():
    """The routing rule that caused the mis-route must be explicit: a quoted
    line containing 'stock' is a vendor offer, not warehouse inventory."""
    from core.chat_tool_planner import _PLANNER_SYSTEM

    low = _PLANNER_SYSTEM.lower()
    # Re-contracted 2026-09-16 (audit item 4): the route is
    # PROVENANCE-determined, not unconditionally mail.
    assert "pasted / quoted text routes by provenance" in low
    assert 'just because it contains words like "stock"' in low
    assert "record apps even when they repeat a" in low
    assert "genuine own-record questions" in low
    assert "quantities on hand" in low


# --------------------------------------------------------------------------- #
# FIGURE GROUNDING — invented arithmetic must not ship
# --------------------------------------------------------------------------- #

def test_invented_derivation_figures_are_detected():
    """Live 2026-09-15: asked how the $8,880 list price was derived, the reply
    presented "$5,350 → +10% → $5,885 → ÷0.70 → $8,407 → +$473 → $8,880" as
    the calculation. The cited workbook row holds 5350/4815/5515/5625.30/
    6465.86/7518.44/7519 — every intermediate was invented, and 8,880 is a
    different machine's list price."""
    from core.chat_tool_planner import _unsupported_figures

    evidence = (
        "- [document] PRICE VIPUL (6).xlsx | L315: R235 | F-52\"x16G | 7519.0 | "
        "5350 | 4815.0 | 5515.0 | 5625.3 | 6465.862068965517 | 7518.444266238974"
    )
    reply = (
        "Step 1: Dealer list $5,350.00\n"
        "+10% freight = $5,885.00\n"
        "÷ 0.70 (30% margin) = $8,407.14\n"
        "+ $473 google-review markup = $8,880.00"
    )

    flagged = _unsupported_figures(reply, evidence)

    assert "$5,885.00" in flagged
    assert "$8,407.14" in flagged
    assert "$8,880.00" in flagged
    assert "$5,350.00" not in flagged, "a figure present in the evidence must not be flagged"


def test_grounded_derivation_is_not_flagged():
    from core.chat_tool_planner import _unsupported_figures

    # the freight figure is evidence too — the thread says "700 for freight"
    evidence = ("R235 | F-52\"x16G | 5350 | 4815.0 | 5515.0 | 5625.3 | 6465.86 "
                "| 7518.44 | 7519.0\n- [ingested mailbox] Vipul: 700 for freight and 0 csa")
    reply = (
        "Row 235 derives it: $5,350.00 less 10% = $4,815.00, + $700 freight = "
        "$5,515.00, then the margin steps give $7,519.00."
    )

    assert _unsupported_figures(reply, evidence) == []


def test_user_supplied_figures_are_grounded_by_their_own_message():
    """The guard compares against evidence AND the user's message, so echoing
    a figure the customer just quoted is never treated as invented."""
    from core.chat_tool_planner import _unsupported_figures

    message = "here's their offer: $12,345.67 net"
    reply = "Their quote was $12,345.67 net — shall I match it?"

    assert _unsupported_figures(reply, f"unrelated evidence\n{message}") == []


def test_bare_small_numbers_are_not_money_claims():
    """Years, quantities and counts must not trip the detector."""
    from core.chat_tool_planner import _unsupported_figures

    reply = "I checked 12 messages from 2026 and found 3 threads."

    assert _unsupported_figures(reply, "evidence with no figures") == []


# --------------------------------------------------------------------------- #
# FABRICATION AS A ROUTING SIGNAL (hallucination score for BPC/BYOK)
# --------------------------------------------------------------------------- #
#
# The models BPC picks vary wildly in how much they invent. The learning
# router already re-ranks BPC's candidate list by observed per-model
# satisfaction — but its signal set was truncation / refusal / schema / empty /
# exception, so FABRICATION was invisible: a model could invent prices on every
# turn and keep winning the routing. These pin the new signal.


def test_fabrication_scores_worst_and_is_named():
    from core.llm.response_quality import assess_response_quality

    fabricated = assess_response_quality(
        content="here is the derivation", unsupported_figures=["$8,880.00"]
    )
    ungrounded = assess_response_quality(
        content="here is the derivation", ungrounded_claims=["claimed a 5% fee"]
    )
    truncated = assess_response_quality(content="half a sen", finish_reason="length")
    refusal = assess_response_quality(content="I am sorry, but I cannot help with that.")
    clean = assess_response_quality(content="Row 235 lists 7519.0 CAD.")

    assert fabricated.issues == ["unsupported_figures"]
    assert ungrounded.issues == ["ungrounded_claims"]
    assert fabricated.quality_satisfied is False
    # Fabrication must rank BELOW the failures a user can SEE are incomplete.
    assert fabricated.quality_score < truncated.quality_score
    assert fabricated.quality_score < refusal.quality_score
    assert clean.quality_satisfied is True


def test_fabrication_feedback_feeds_the_per_model_predictor():
    """The label must reach the trainer, not just the log."""
    from core.learning_llm_router import LearningBasedRouter
    from core.llm.response_quality import assess_response_quality

    quality = assess_response_quality(
        content="x", unsupported_figures=["$8,880.00"]
    )
    fb = LearningBasedRouter.build_feedback(
        routing_result_id="r1", tenant_id="default",
        model_id="provider/inventor", task_type="question_answering",
        quality=quality,
    )

    assert fb.quality_satisfied is False
    assert fb.user_satisfaction == quality.quality_score


def test_fabrication_signal_records_even_with_routing_flag_off(monkeypatch):
    """ATOM_LEARNING_ROUTER gates RE-RANKING, not observation: with the flag
    off the fabrication row must still be written, or flipping the flag on
    later starts from an empty table and the hallucination history is lost."""
    import asyncio

    import core.llm.learning_router_registry as reg

    written = {}

    class _Router:
        def _persist_feedback(self, feedback, features):
            written["row"] = feedback

    monkeypatch.setattr(reg, "get_learning_router_instance", lambda: None)
    # Patch the METHOD, not __new__: monkeypatch restores a patched __new__ as
    # an OWN class attribute, after which type.__call__ stops treating it as
    # the default and passes the constructor args to object.__new__ — every
    # LATER test that builds a LearningBasedRouter then dies with
    # "object.__new__() takes exactly one argument". Reproduced at HEAD.
    monkeypatch.setattr(
        "core.learning_llm_router.LearningBasedRouter._persist_feedback",
        lambda _self, feedback, features: written.__setitem__("row", feedback),
    )

    ok = asyncio.run(reg.record_fabrication_signal(
        model_id="provider/inventor", task_type="question_answering",
        unsupported_figures=["$8,880.00"],
    ))

    assert ok is True
    assert written["row"].model_id == "provider/inventor"
    assert written["row"].quality_satisfied is False


def test_clean_reply_records_no_fabrication_signal(monkeypatch):
    """A verdict-less call must be a pure no-op — no row, no router work."""
    import asyncio

    import core.llm.learning_router_registry as reg

    writes = []
    monkeypatch.setattr(
        "core.learning_llm_router.LearningBasedRouter._persist_feedback",
        lambda _self, fb, feats: writes.append(fb),
    )

    ok = asyncio.run(reg.record_fabrication_signal(model_id="m"))

    assert ok is False
    assert writes == [], "a clean verdict must not write a fabrication row"
