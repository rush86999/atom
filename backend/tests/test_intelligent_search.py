"""Intelligent search queries — the execution-time guarantee that every
agent's searches name the subject, whatever the planning model wrote.

Live incident (2026-09-01): "research the lead over the web to determine if
end user or dealer" reached Tavily as "determine if lead is end user or
dealer" — results about the METAL lead. The query must resolve "the lead"
to the actual names from the conversation or the open canvas.
"""
import pytest

from core.intelligent_search import build_search_query, _entities

HISTORY = [
    {"message": "check if end user or dealer and then confirm my corrections",
     "response": {"message": "I can see you're drafting an initial contact to Jacob at Blumetric."}},
    {"message": "how did the contact form submission help you determine it's an end user?",
     "response": {"message": "I was inferring based on the email address (@blumetric.ca)."}},
]

CANVAS = {
    "to": "jschulz@blumetric.ca",
    "cc": "vipul@brennan.ca",
    "subject": "Brennan Machinery | Following Up on Your Inquiry",
    "body": "Hi Jacob, Rish here from Brennan Machinery.",
}


# ───────────────────────── entity extraction ─────────────────────────

def test_entities_capture_names_emails_and_drop_common_words():
    text = ("Hi Rish, check if Blumetric and Jacob Schulz are dealers. "
            "Email jschulz@blumetric.ca or visit https://www.brennan.ca")
    ents = [e.lower() for e in _entities(text)]
    assert "blumetric" in ents
    assert "jacob schulz" in ents
    assert "blumetric" in ents  # from the email domain
    assert "brennan" in ents    # from the URL host
    assert "check" not in ents and "hi" not in ents


def test_entities_empty_for_plain_instructions():
    assert _entities("research the lead over the web") == []


# ───────────────────────── query building ─────────────────────────

def test_generic_noun_query_resolves_entity_from_history():
    q = build_search_query(
        "research the lead over the web to determine if end user or dealer",
        history_turns=HISTORY,
        canvas_content=CANVAS,
    )
    assert "blumetric" in q.lower()
    assert "jacob" in q.lower() or "schulz" in q.lower()
    # the user's actual question survives as search intent
    assert "end user" in q.lower() or "dealer" in q.lower()
    # instruction scaffolding does not
    assert "research" not in q.lower() and "over the web" not in q.lower()


def test_entity_in_message_beats_context_resolution():
    q = build_search_query(
        "research Acme Industrial over the web — are they a dealer?",
        history_turns=HISTORY,
        canvas_content=CANVAS,
    )
    assert "acme industrial" in q.lower()
    assert "blumetric" not in q.lower()  # context entity NOT injected


def test_canvas_fields_resolve_when_history_is_thin():
    q = build_search_query(
        "determine if this company is an end user or dealer",
        history_turns=[],
        canvas_content=CANVAS,
    )
    assert "blumetric" in q.lower() or "brennan" in q.lower()


def test_no_entities_anywhere_returns_cleaned_message():
    q = build_search_query(
        "research the weather over the web",
        history_turns=[{"message": "hello", "response": {"message": "hi"}}],
        canvas_content={"to": "", "subject": "", "body": ""},
    )
    assert q == "the lead weather" or "weather" in q
    assert "research" not in q.lower() and "over the web" not in q.lower()


def test_query_length_capped_on_word_boundary():
    long_history = [{"message": "Met with " + "Verylongname " * 40,
                     "response": {"message": ""}}]
    q = build_search_query(
        "research them over the web",
        history_turns=long_history,
        max_length=120,
    )
    assert len(q) <= 120


# ───────────────────────── execution-path wiring ─────────────────────────

@pytest.mark.asyncio
async def test_execute_tool_plan_rewrites_generic_web_query():
    """The rewrite happens at EXECUTION time — even a weak planning model's
    generic query gets the subject resolved before Tavily is called."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from core.chat_tool_planner import ToolPlan, execute_tool_plan

    plan = ToolPlan(use_tool=True, service="web_search", intent="search",
                    query="determine if lead is end user or dealer")
    captured = {}

    async def fake_web_search(query, tenant_id):
        captured["query"] = query
        return {"answer": "BluMetric is an environmental firm.", "results": []}

    with patch("integrations.mcp_service.mcp_service") as mcp:
        mcp.web_search = AsyncMock(side_effect=fake_web_search)
        block = await execute_tool_plan(
            plan, "user-1", "default",
            context={"history": HISTORY, "canvas": CANVAS},
        )
    assert "blumetric" in captured["query"].lower()
    assert block and "LIVE TOOL RESULTS" in block
    assert "environmental firm" in block


# ───────────────── grounding guard (model-quality wobble) ─────────────────

def test_reply_inability_detector_patterns():
    from integrations.chat_orchestrator import _reply_claims_inability
    # the LIVE wobble: claims inability while research results were injected
    assert _reply_claims_inability(
        "I don't have the ability to research Blumetric directly over the web.")
    assert _reply_claims_inability(
        "I'm unable to research that lead over the web to determine their type.")
    assert _reply_claims_inability("I do not have access to web search.")
    # legitimate content answers must NOT trip the detector
    assert not _reply_claims_inability(
        "Based on my research, BluMetric is an end user — an environmental firm.")
    assert not _reply_claims_inability(
        "Here's the follow-up draft emphasizing technical support.")


def test_grounding_guard_constants_shape():
    """The guard is wired into _get_qwen_response for BOTH reply paths."""
    import inspect
    from integrations import chat_orchestrator as co
    src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
    assert src.count("_reply_claims_inability") >= 2  # streaming + non-stream paths
    assert "LIVE TOOL RESULT block IS present" in src
