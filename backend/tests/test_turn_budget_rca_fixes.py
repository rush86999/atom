# -*- coding: utf-8 -*-
"""Turn-budget RCA fixes (2026-09-22 "rebuild the draft" turn).

Four pinned behaviors:
1. Edit-shaped canvas-panel turns get the extended (derivation-class)
   budget — the measured 95s chain ended in turn_budget_exceeded.
2. The planner's relevance verdicts consume history, and an approval that
   RESTATES the offered task resolves to that exchange — no second
   corrective structured call (the 59.5s planner).
3. When the canvas-edit leg dies at its bound, the action leg is skipped
   unless an action plan is already in flight.
4. The per-model rate budget reserves a headroom fraction for interactive
   chat-context calls; background calls are admitted only above it.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fix 1 — extended budget class for edit-shaped canvas turns
# ---------------------------------------------------------------------------

class TestCanvasEditShapeBudget:
    def test_incident_message_is_edit_shaped_with_canvas(self):
        from integrations.chat_orchestrator import _canvas_edit_shaped

        assert _canvas_edit_shaped(
            "rebuild the draft with requested quotes and alternatives to "
            "those machinery.", {"canvas_id": "c1", "canvas_type": "email"})

    def test_edit_verbs_without_canvas_stay_ordinary(self):
        from integrations.chat_orchestrator import _canvas_edit_shaped

        assert not _canvas_edit_shaped("rebuild the draft", {})
        assert not _canvas_edit_shaped("update the table", None)

    def test_plain_questions_stay_ordinary_even_on_canvas(self):
        from integrations.chat_orchestrator import _canvas_edit_shaped

        assert not _canvas_edit_shaped(
            "what does the draft say?", {"canvas_id": "c1"})

    def test_extended_budget_applies(self, monkeypatch):
        monkeypatch.delenv("ATOM_CHAT_REQUEST_DEADLINE_SECONDS", raising=False)
        monkeypatch.delenv("ATOM_DERIVATION_TURN_BUDGET_SECONDS", raising=False)
        from integrations.chat_orchestrator import (
            CHAT_DERIVATION_TURN_BUDGET_SECONDS,
            _canvas_edit_shaped,
            _derivation_ask,
            _request_deadline_seconds,
        )

        msg = ("rebuild the draft with requested quotes and alternatives to "
               "those machinery.")
        ctx = {"canvas_id": "c1"}
        assert _request_deadline_seconds(
            derivation=_derivation_ask(msg, {"history": [], "canvas": ctx})
            or _canvas_edit_shaped(msg, ctx)
        ) == CHAT_DERIVATION_TURN_BUDGET_SECONDS

    def test_canvas_leg_cap_scales_with_budget_class(self):
        """Gap A follow-up (2026-09-22): raising the total budget alone left
        the edit leg capped at 45s — the turn answered in CHAT while the
        canvas never changed. Extended-class budgets get the extended cap."""
        from integrations.chat_orchestrator import (
            CHAT_TURN_BUDGET_DEFAULT_SECONDS,
            TurnDeadline,
            _CANVAS_LEG_MAX_EXTENDED_SECONDS,
            _CANVAS_LEG_MAX_SECONDS,
            _canvas_leg_cap,
        )

        assert _canvas_leg_cap(TurnDeadline(115)) == (
            _CANVAS_LEG_MAX_EXTENDED_SECONDS)
        assert _canvas_leg_cap(
            TurnDeadline(CHAT_TURN_BUDGET_DEFAULT_SECONDS)
        ) == _CANVAS_LEG_MAX_SECONDS
        # Disabled/zero deadlines keep the ordinary cap.
        assert _canvas_leg_cap(TurnDeadline(0)) == _CANVAS_LEG_MAX_SECONDS

    def test_extended_cap_keeps_the_reply_reserve(self, monkeypatch):
        monkeypatch.delenv(
            "ATOM_CANVAS_LEG_MAX_EXTENDED_SECONDS", raising=False)
        monkeypatch.delenv("ATOM_REPLY_LEG_MIN_SECONDS", raising=False)
        from integrations.chat_orchestrator import (
            _REPLY_LEG_MIN_SECONDS,
            TurnDeadline,
            _canvas_leg_cap,
            _pre_reply_leg_timeout,
        )

        # On a 115s budget the edit leg's WAIT must still leave the reply
        # leg at least its 40s floor.
        deadline = TurnDeadline(115)
        wait = _pre_reply_leg_timeout(deadline, _canvas_leg_cap(deadline))
        assert (deadline.total_seconds - wait
                >= _REPLY_LEG_MIN_SECONDS - 0.5)


# ---------------------------------------------------------------------------
# Fix 2 — restated approvals resolve; planner verdicts consume history
# ---------------------------------------------------------------------------

OFFER_HISTORY = [
    {"message": "search my email for Steve Macisaac machinery requested",
     "response": {"message": (
         "Here are the eight machines. If you want, I'll rebuild the canvas "
         "table with the full eight-line list (or a main pick plus the "
         "slitter alternatives) and restore the footer.")}},
]
REBUILD_MSG = ("rebuild the draft with requested quotes and alternatives "
               "to those machinery.")


class TestRestatedApprovalResolution:
    def test_the_incident_message_resolves_to_the_offer_exchange(self):
        from core.plan_relevance import (
            REF_RESOLVED,
            resolve_request_reference,
        )

        ref = resolve_request_reference(REBUILD_MSG, OFFER_HISTORY)
        assert ref.kind == REF_RESOLVED
        assert ref.clarify_reason == "offer_restatement"
        assert any("Steve Macisaac" in r for r in ref.lineage_requests)
        # The current message leads the topic (constraints preserved).
        assert ref.topic_text.startswith(REBUILD_MSG)

    def test_single_shared_word_does_not_ground(self):
        from core.plan_relevance import REF_DIRECT, resolve_request_reference

        history = [{"message": "m",
                    "response": {"message": "I can rebuild the engine."}}]
        assert resolve_request_reference(
            "rebuild the porch", history).kind == REF_DIRECT

    def test_no_history_stays_direct(self):
        from core.plan_relevance import REF_DIRECT, resolve_request_reference

        assert resolve_request_reference(REBUILD_MSG, None).kind == REF_DIRECT

    def test_fulfilled_offer_does_not_ground_a_restatement(self):
        from core.plan_relevance import REF_DIRECT, resolve_request_reference

        history = OFFER_HISTORY + [
            {"message": "yes go ahead",
             "response": {"message": "Here is the rebuilt table."}},
        ]
        # The offer was delivered; a later task sharing its wording is a NEW
        # ask, not an approval of a dead offer.
        assert resolve_request_reference(REBUILD_MSG, history).kind == REF_DIRECT


class TestPlannerVerdictUsesHistory:
    def test_incident_first_plan_query_is_relevant_with_history(self):
        """The exact RCA shape: no repair arm fires, so the planner makes
        ONE structured call instead of two."""
        from core.chat_tool_planner import _plan_relevance_verdict

        assert _plan_relevance_verdict(
            "Steve Macisaac machinery requested", REBUILD_MSG,
            OFFER_HISTORY) == "relevant"

    def test_query_about_the_offered_subject_needs_history(self):
        """The incident mechanism: a plan about the OFFERED subject shares no
        token with the restating message — irrelevant judged bare (the
        repair arm fired, doubling planner latency), relevant on the
        resolved topic."""
        from core.chat_tool_planner import _plan_relevance_verdict

        # "slitter footer table" appear only in the OFFER text, never in
        # the message itself.
        assert _plan_relevance_verdict(
            "slitter footer table", REBUILD_MSG) == "irrelevant"
        assert _plan_relevance_verdict(
            "slitter footer table", REBUILD_MSG, OFFER_HISTORY) == "relevant"

    def test_the_stamp_basis_is_real_not_module_unavailable(self):
        """R4's stamp wrapper imported a function that never existed — every
        plan was silently stamped ('unknown', 'module-unavailable'). The
        basis is now a real rule name."""
        from core.chat_tool_planner import _plan_relevance_basis
        from core.plan_relevance import relevance_basis

        verdict, basis = relevance_basis(
            "vendor scorecard workbook", "open the vendor scorecard workbook")
        assert verdict == "relevant"
        assert basis not in ("", "module-unavailable")
        assert _plan_relevance_basis(
            "vendor scorecard workbook", "open the vendor scorecard workbook"
        ) == (verdict, basis)


# ---------------------------------------------------------------------------
# Fix 3 — action leg skipped after a doomed edit leg
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_action_leg_skipped_when_edit_leg_dies_at_bound(monkeypatch):
    import integrations.chat_orchestrator as chat

    monkeypatch.setenv("ATOM_CHAT_REQUEST_DEADLINE_SECONDS", "8")
    monkeypatch.setattr(chat, "_CANVAS_LEG_MAX_SECONDS", 0.5)
    monkeypatch.setattr(chat, "_REPLY_LEG_MIN_SECONDS", 1.0)

    orch = chat.ChatOrchestrator()
    session = {"id": "sess-rca3", "history": []}
    canvas = {"canvas_id": "c1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}

    async def slow_edit(*a, **k):
        await asyncio.sleep(5)  # dies at the 0.5s bound
        return None

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_try_canvas_edit", side_effect=slow_edit),
        patch.object(orch, "_try_canvas_action",
                     new=AsyncMock()) as action,
        patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
            "content": "answered from the tool path", "model": "m",
            "provider": "p"})),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
    ):
        result = await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-rca3",
            context={"canvas_id": "c1"})

    action.assert_not_awaited()
    assert result["message"] == "answered from the tool path"


@pytest.mark.asyncio
async def test_action_leg_runs_when_an_action_task_is_in_flight(monkeypatch):
    """The skip only applies when no action plan exists — a healthy edit leg
    pre-starts one, and that plan is still joined."""
    import integrations.chat_orchestrator as chat

    monkeypatch.setenv("ATOM_CHAT_REQUEST_DEADLINE_SECONDS", "8")
    monkeypatch.setattr(chat, "_CANVAS_LEG_MAX_SECONDS", 0.5)
    monkeypatch.setattr(chat, "_REPLY_LEG_MIN_SECONDS", 1.0)

    orch = chat.ChatOrchestrator()
    session = {"id": "sess-rca4", "history": []}
    canvas = {"canvas_id": "c1", "canvas_type": "email",
              "content": {"subject": "Draft", "body": "Unchanged"}}

    async def slow_edit(message, history, canvas, *a, shared_tool_state=None, **k):
        # A healthy edit leg pre-starts the action plan before it dies.
        if shared_tool_state is not None:
            shared_tool_state["action_plan_task"] = asyncio.ensure_future(
                asyncio.sleep(0))
        await asyncio.sleep(5)
        return None

    with (
        patch.object(orch, "_get_or_create_session", return_value=session),
        patch.object(orch, "_resolve_canvas_ctx",
                     new=AsyncMock(return_value=canvas)),
        patch.object(orch, "_start_chat_execution", return_value="e1"),
        patch.object(orch, "_record_chat_step", new=AsyncMock()),
        patch.object(orch, "_emit_agent_status", new=AsyncMock()),
        patch.object(orch, "_finish_chat_execution"),
        patch.object(orch, "_update_session"),
        patch.object(orch, "_try_canvas_edit", side_effect=slow_edit),
        patch.object(orch, "_try_canvas_action",
                     new=AsyncMock(return_value=None)) as action,
        patch.object(orch, "_get_qwen_response", new=AsyncMock(return_value={
            "content": "ok", "model": "m", "provider": "p"})),
        patch("core.chat_tool_planner.plan_tool_use",
              new=AsyncMock(return_value=None)),
        patch("core.chat_tool_planner._provenance_menu",
              new=AsyncMock(return_value="")),
    ):
        await orch.process_chat_message(
            "u1", "rebuild the draft with the quotes", "sess-rca4",
            context={"canvas_id": "c1"})

    action.assert_awaited()


# ---------------------------------------------------------------------------
# Fix 4 — interactive rate reserve
# ---------------------------------------------------------------------------

class TestInteractiveReserve:
    def test_reserve_defaults_and_env_override(self, monkeypatch):
        from core.llm.interactive_context import interactive_rate_reserve

        monkeypatch.delenv("ATOM_INTERACTIVE_RATE_RESERVE", raising=False)
        assert interactive_rate_reserve() == 0.2
        monkeypatch.setenv("ATOM_INTERACTIVE_RATE_RESERVE", "0.5")
        assert interactive_rate_reserve() == 0.5
        monkeypatch.setenv("ATOM_INTERACTIVE_RATE_RESERVE", "0")  # disable
        assert interactive_rate_reserve() == 0.0

    def test_scope_marks_and_resets(self):
        from core.llm.interactive_context import (
            is_interactive_chat,
            mark_interactive_chat,
            reset_interactive_chat,
        )

        assert not is_interactive_chat()
        token = mark_interactive_chat()
        assert is_interactive_chat()
        reset_interactive_chat(token)
        assert not is_interactive_chat()

    def test_tasks_spawned_after_reset_are_background_again(self):
        """Fire-and-forget work dispatched at turn end (after the finally)
        must NOT inherit the interactive classification."""
        import asyncio

        from core.llm.interactive_context import (
            is_interactive_chat,
            mark_interactive_chat,
            reset_interactive_chat,
        )

        async def main():
            token = mark_interactive_chat()
            assert is_interactive_chat()
            reset_interactive_chat(token)
            seen = []

            async def bg():
                seen.append(is_interactive_chat())

            t = asyncio.ensure_future(bg())
            await t
            return seen

        assert asyncio.run(main()) == [False]


class TestBpcAdmissionReserve:
    """The reserve gate inside BPC ranking: background-context calls are
    skipped below the reserve; interactive calls are admitted to the floor."""

    def _ranked(self, handler, task_type=None):
        from core.llm.byok_handler import QueryComplexity

        return list(handler.get_ranked_providers(
            QueryComplexity.MODERATE, task_type, True, "free", False,
            requires_tools=True, requires_structured=True,
            estimated_tokens=3000,
        ))

    def _patched_tracker(self, monkeypatch, handler, model_headroom):
        from types import SimpleNamespace

        fake = SimpleNamespace(
            get_model_headroom=lambda p, m: model_headroom,
            get_headroom=lambda p: 1.0,
            get_model_weight=lambda p, m: 1.0,
            get_max_context=lambda p, m=200000: 200000,
        )
        monkeypatch.setattr(handler, "rate_tracker", fake)

    def test_background_call_skipped_below_reserve(self, monkeypatch):
        from core.llm.byok_handler import BYOKHandler
        from core.llm.interactive_context import interactive_rate_reserve

        monkeypatch.delenv("ATOM_INTERACTIVE_RATE_RESERVE", raising=False)
        handler = BYOKHandler(workspace_id="default")
        # Headroom sits between 0 and the reserve: interactive calls are
        # admitted, background calls must be skipped.
        self._patched_tracker(
            monkeypatch, handler, interactive_rate_reserve() / 2.0)
        assert self._ranked(handler, "planning") == []

    def test_interactive_call_admitted_to_the_floor(self, monkeypatch):
        from core.llm.byok_handler import BYOKHandler
        from core.llm.interactive_context import (
            interactive_rate_reserve,
            mark_interactive_chat,
            reset_interactive_chat,
        )

        monkeypatch.delenv("ATOM_INTERACTIVE_RATE_RESERVE", raising=False)
        handler = BYOKHandler(workspace_id="default")
        self._patched_tracker(
            monkeypatch, handler, interactive_rate_reserve() / 2.0)
        token = mark_interactive_chat()
        try:
            ranked = self._ranked(handler, "planning")
        finally:
            reset_interactive_chat(token)
        assert ranked, "interactive calls are admitted below the reserve"


class TestPairMemoPersistence:
    """Durable per-pair constraint memos: restarts must not re-pay every
    400 discovery (live 2026-09-22: a fresh boot's first edit turn burned
    its planner budget rediscovering kimi's temperature lock and
    tool_choice/thinking conflict)."""

    def test_save_then_reload_round_trips(self, tmp_path, monkeypatch):
        import json

        memo_path = tmp_path / "pair_memos.json"
        monkeypatch.setenv("ATOM_PAIR_MEMO_PATH", str(memo_path))
        import core.llm.byok_handler as bh

        bh._MODEL_TEMPERATURE["prov/tlocked"] = 1.0
        bh._TOOLCHOICE_UNSUPPORTED.add("prov/thinking")
        bh._REASONING_MANDATORY.add("prov/rmand")
        bh._LOGPROBS_UNSUPPORTED.add("prov/logp")
        bh._AUTH_FAILED.add("prov/badcred")
        bh._save_pair_memos()

        # Simulate the restart: wipe, reload, verify.
        bh._MODEL_TEMPERATURE.clear()
        bh._TOOLCHOICE_UNSUPPORTED.clear()
        bh._REASONING_MANDATORY.clear()
        bh._LOGPROBS_UNSUPPORTED.clear()
        bh._AUTH_FAILED.clear()
        bh._load_pair_memos()
        assert bh._MODEL_TEMPERATURE["prov/tlocked"] == 1.0
        assert bh._TOOLCHOICE_UNSUPPORTED == {"prov/thinking"}
        assert bh._REASONING_MANDATORY == {"prov/rmand"}
        assert bh._LOGPROBS_UNSUPPORTED == {"prov/logp"}
        assert bh._AUTH_FAILED == {"prov/badcred"}
        # The file on disk is plain JSON (inspectable, hand-editable).
        payload = json.loads(memo_path.read_text())
        assert payload["temperature"] == {"prov/tlocked": 1.0}

    def test_missing_file_is_a_cold_start(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            "ATOM_PAIR_MEMO_PATH", str(tmp_path / "nonexistent.json"))
        import core.llm.byok_handler as bh

        bh._MODEL_TEMPERATURE.clear()
        bh._load_pair_memos()  # must not raise, must not invent entries
        assert bh._MODEL_TEMPERATURE == {}
