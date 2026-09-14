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

    assert block and "5,350.00" in block
    assert "LIVE TOOL RESULTS" in block
    assert "no live integration lookup was attempted" in block
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

    def fake_tokens(user_id, tokens, limit=4):
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
    """No distinctive figure → no store walk at all (the common case)."""
    import asyncio

    import core.chat_tool_planner as ctp
    from integrations.chat_orchestrator import _verbatim_mail_evidence

    def boom(*a, **k):
        raise AssertionError("must not scan for a figure-less message")

    monkeypatch.setattr(ctp, "_search_ingested_by_tokens", boom)

    assert asyncio.run(
        _verbatim_mail_evidence("what did Sarah say about the deadline", "u1", {})
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
    assert "never present it as the reason the item could not be found" in note


def test_planner_prompt_forbids_pasted_quotes_going_to_inventory():
    """The routing rule that caused the mis-route must be explicit: a quoted
    line containing 'stock' is a vendor offer, not warehouse inventory."""
    from core.chat_tool_planner import _PLANNER_SYSTEM

    low = _PLANNER_SYSTEM.lower()
    assert "pasted / quoted text is mail" in low
    assert 'even when the quote contains the word "stock"' in low
    assert "not to zoho_inventory" in low
    assert "quantities on hand" in low
