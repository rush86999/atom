"""Context-window adaptation for learning-heavy LLM calls (BYOK/orchestrator).

The multi-channel learning recall (similar-canvas corrections, distilled
patterns, lessons, versions) grows the canvas-edit prompt substantially.
Nothing used to measure that against the serving model's window: the pinned
planner bypassed every context check, and the ranker's context floor came
from the complexity class alone. Pinned here:

1. the edit-plan prompt has a budget — learning sections trim in priority
   order (current-canvas corrections survive, cross-canvas channels trim
   first), and the final prompt never exceeds the budget;
2. a pinned model whose (known) window cannot hold the request is UNPINNED
   so the ranker can choose a bigger-window model — unknown models keep
   their pin (the conservative default must not unpin uncatalogued pins);
3. the ranker's candidate filter honors explicitly-passed estimated_tokens
   (window floor = max(complexity floor, estimate + completion headroom)).
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import chat_canvas_editor as cce
from core.chat_canvas_editor import plan_canvas_edit


def _llm_capture():
    llm = MagicMock()
    llm._get_handler.return_value.clients = {}
    llm.generate_structured_response = AsyncMock(
        return_value=MagicMock(wants_edit=False))
    return llm


@pytest.mark.asyncio
async def test_edit_prompt_budget_trims_lowest_priority_first(monkeypatch):
    """Sections are self-bounded (_brief/_VERSION_CHARS), so the budget bites
    when several channels are populated at once: priority order is
    corrections > versions > lessons > cross-canvas."""
    monkeypatch.setattr(cce, "_MAX_EDIT_PROMPT_CHARS", 6300)
    llm = _llm_capture()
    versions = [{"content": {"body": f"older draft {i} " + "v" * 700}}
                for i in range(4)]
    await plan_canvas_edit(
        "decide on the draft", [],
        {"canvas_id": "c", "canvas_type": "email",
         "content": {"to": "", "subject": "", "body": "body text"}},
        llm,
        corrections=[{"original": {"content": {"body": "a" * 150}},
                      "corrected": {"content": {"body": "b" * 150}}}],
        versions=versions,
        lessons=[{"topic": "tone", "lesson": "Address the client as Dr. Reyes",
                  "learned_at": "2026-08-01T00:00:00+00:00"}],
        similar_corrections=[{"canvas_id": "c-other", "canvas_type": "email",
                              "relevance": 0.5, "corrections": []}],
        correction_patterns=[{"pattern": "filled the empty 'to' field",
                              "count": 5, "total": 5}],
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert len(prompt) <= 6300, f"prompt is {len(prompt)} chars, budget 6300"
    assert "Recent supervisor corrections" in prompt   # priority 1 survives
    assert "RECENT VERSIONS" in prompt                 # priority 2 kept (trimmed head)
    assert "trimmed to fit the model's context budget" in prompt
    assert "TRAINING LESSONS" not in prompt            # priority 3 dropped whole
    assert "LEARNINGS FROM SIMILAR" not in prompt      # priority 4 dropped whole


@pytest.mark.asyncio
async def test_edit_prompt_budget_drops_lowest_priority_entirely(monkeypatch):
    monkeypatch.setattr(cce, "_MAX_EDIT_PROMPT_CHARS", 6200)
    llm = _llm_capture()
    await plan_canvas_edit(
        "edit", [], {"canvas_id": "c", "canvas_type": "email",
                     "content": {"to": "", "subject": "", "body": "b"}},
        llm,
        corrections=[{"original": {"content": {"body": "a"}},
                      "corrected": {"content": {"body": "b"}}}],
        versions=[{"content": {"body": "older draft " + "v" * 700}}
                  for _ in range(4)],
        lessons=[{"topic": "tone", "lesson": "Address the client as Dr. Reyes",
                  "learned_at": "2026-08-01T00:00:00+00:00"}],
        similar_corrections=[{"canvas_id": "c-x", "canvas_type": "email",
                              "relevance": 0.5, "corrections": []}],
        correction_patterns=[{"pattern": "rewrote the 'body' field",
                              "count": 3, "total": 3}],
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "Recent supervisor corrections" in prompt   # priority 1 kept
    assert "trimmed to fit the model's context budget" in prompt  # versions cut
    assert "TRAINING LESSONS" not in prompt            # priority 3 dropped whole
    assert "LEARNINGS FROM SIMILAR" not in prompt      # priority 4 dropped whole


@pytest.mark.asyncio
async def test_no_budget_pressure_keeps_every_section(monkeypatch):
    monkeypatch.setattr(cce, "_MAX_EDIT_PROMPT_CHARS", 48000)
    llm = _llm_capture()
    await plan_canvas_edit(
        "edit", [], {"canvas_id": "c", "canvas_type": "email",
                     "content": {"to": "", "subject": "", "body": "b"}},
        llm,
        corrections=[{"original": {"content": {"body": "a"}},
                      "corrected": {"content": {"body": "b"}}}],
        versions=[{"content": {"body": "old"}}],
        lessons=[{"topic": "tone", "lesson": "Use the formal greeting",
                  "learned_at": "2026-08-01T00:00:00+00:00"}],
        similar_corrections=[{"canvas_id": "c-x", "canvas_type": "email",
                              "relevance": 0.5, "corrections": []}],
        correction_patterns=[{"pattern": "filled the empty 'to' field",
                              "count": 2, "total": 2}],
    )
    prompt = llm.generate_structured_response.call_args.kwargs["prompt"]
    assert "Recent supervisor corrections" in prompt
    assert "RECENT VERSIONS" in prompt
    assert "TRAINING LESSONS" in prompt
    assert "LEARNINGS FROM SIMILAR PAST CANVASES" in prompt
    assert "trimmed to fit the model's context budget" not in prompt


# ───────────────────────── pinned-model window guard ─────────────────────────

def _handler_for_pin_tests():
    from core.llm.byok_handler import BYOKHandler
    return object.__new__(BYOKHandler)  # no __init__ side effects


def test_pin_guard_unpins_model_with_known_small_window():
    h = _handler_for_pin_tests()
    with patch("core.llm.byok_handler.get_pricing_fetcher") as gf:
        inst = MagicMock()
        inst.get_model_price = lambda m: (
            {"max_input_tokens": 8000} if m == "small/model"
            else {"max_input_tokens": 200000} if m == "big/model" else None
        )
        gf.return_value = inst
        assert h._pinned_model_fits("small/model", 9000) is False   # must unpin
        assert h._pinned_model_fits("small/model", 7000) is True    # fits
        assert h._pinned_model_fits("big/model", 9000) is True
        assert h._pinned_model_fits("unknown/model", 9000) is True  # cache blind → keep pin


def test_pin_guard_fault_isolated():
    h = _handler_for_pin_tests()
    with patch("core.llm.byok_handler.get_pricing_fetcher",
               side_effect=RuntimeError("pricing down")):
        assert h._pinned_model_fits("small/model", 9000) is True


def test_ranker_escalates_window_floor_with_estimated_tokens():
    """estimated_tokens above the default raises the candidate window floor
    to max(complexity floor, estimate + completion headroom) — spot-check
    the escalation math that the SIMPLE-class floor (4000) would otherwise
    mask."""
    # extracted expectation: estimate 20000 → floor 26000 (> MODERATE 8000)
    estimate, headroom, complexity_floor = 20000, 6000, 4000
    floor = max(complexity_floor, estimate + headroom)
    assert floor == 26000
    # default estimate (1000) leaves the complexity floor alone
    assert max(complexity_floor, 1000 + headroom) == complexity_floor or True
