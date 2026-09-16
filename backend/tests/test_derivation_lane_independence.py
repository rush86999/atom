# -*- coding: utf-8 -*-
"""The workbook derivation lane must fire for the ask the incident used.

Live failure this pins (2026-09-16, the original incident ask):

    "open PRICE VIPUL and show how the 7519 listed price was derived"

``_derivation_dataset_block`` builds its probe tokens from
``_distinctive_figure_phrases`` — a CURRENCY/format recogniser. For a bare
integer with no symbol and no grouping it returns nothing, so ``figures`` was
empty, the function returned ``None``, the workbook lane never ran, and the
model answered from memory ("shall I open it now?") or asked the user to share
the file. The case passed only when the canvas happened to carry a formatted
``$7,519.00``, which is why it looked intermittent.

Second failure the same day: the lane was only invoked INSIDE the planner's
plan branches, so a planner timeout skipped it altogether and a derivation ask
was answered from a vacuum.

Both are pinned here, with the dataset store stubbed so the assertions do not
depend on the operator's live catalogues.
"""
import asyncio

import pytest

import integrations.chat_orchestrator as co

ASK = "open PRICE VIPUL and show how the 7519 listed price was derived"


def _hit(file_name="PRICE VIPUL (6).xlsx", row=235):
    return {
        "file_name": file_name,
        "sheet_name": "Sheet1",
        "row_number": row,
        "values": {"Product Name": 'F-52"x16G', "LIST Price": 7519.0},
        "formulas": {"G235": "=F235*0.9", "I235": "=H235+700"},
    }


class _Stub:
    """Records the probe tokens the lane asked for."""

    def __init__(self, hits=None):
        self.tokens = []
        self.hits = hits if hits is not None else [_hit()]

    def __call__(self, token, *args, **kwargs):
        self.tokens.append(token)
        return {"hits": list(self.hits)}


@pytest.fixture()
def stub_store(monkeypatch):
    stub = _Stub()

    import core.sheet_dataset_service as sds
    monkeypatch.setattr(sds, "sheet_datasets_enabled", lambda: True)
    monkeypatch.setattr(sds, "search_all_datasets_sync", stub)
    monkeypatch.setattr(
        sds, "render_dataset_answer",
        lambda hit: (f"SQL RESULT from '{hit['file_name']}' sheet "
                     f"'{hit['sheet_name']}' | R{hit['row_number']} | "
                     "LIST Price=7519.0 | FORMULAS FOR THE MATCHED ROW(S): "
                     "G235==F235*0.9"))
    monkeypatch.setattr(sds, "distinctive_name_tokens",
                        lambda texts, max_tokens=2: [])
    return stub


def _run(message, canvas=None):
    return asyncio.run(co._derivation_dataset_block(
        message, "user-1", {"history": [], "canvas": canvas},
        llm_service=None))


class TestBareIntegerFiguresReachTheWorkbook:
    def test_the_incident_ask_probes_the_bare_integer(self, stub_store):
        block = _run(ASK)
        assert block, "the derivation lane produced no evidence for the ask"
        assert "7519" in block
        assert stub_store.tokens, "no probe was issued at all"
        assert "7519" in stub_store.tokens, (
            f"the bare integer never reached the catalog probe: "
            f"{stub_store.tokens}")

    def test_a_formatted_figure_still_works(self, stub_store):
        block = _run("show how the $7,519.00 listed price was derived")
        assert block and "7519" in block.replace(",", "")

    def test_the_figure_must_sit_next_to_a_value_word(self, stub_store):
        """A stray 4-digit number in a derivation ask is not a probe token."""
        _run("figure out how the shipment reference 4821 was calculated")
        assert "4821" not in stub_store.tokens, (
            "an unqualified integer filled a probe slot")

    def test_a_long_id_is_not_a_figure(self, stub_store):
        _run("show how the 123456789012 listed price was derived")
        assert all(len(t) <= 6 for t in stub_store.tokens), stub_store.tokens

    def test_non_derivation_asks_do_not_probe(self, stub_store):
        assert _run("what is the list price of the F-9999 press?") is None
        assert stub_store.tokens == []

    def test_canvas_figures_still_feed_the_lane(self, stub_store):
        block = _run(ASK, canvas={"body": "quoted $5,350.00 factory"})
        assert block


class TestLaneIndependenceFromThePlanner:
    def test_the_lane_is_invoked_outside_the_plan_branches(self):
        """Shape pin: the guarantee lives in the conversational reply builder
        (`_get_qwen_response` — the single unified path, despite the name),
        AFTER the planner's try/except, so a planner timeout cannot skip the
        lane (measured 2026-09-16)."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        marker = "THE DERIVATION LANE MUST NOT DEPEND ON THE PLANNER SUCCEEDING"
        assert marker in src, "the planner-independent guarantee is gone"
        guard = src.index(marker)
        assert src.index("except Exception as tool_err:") < guard

    def test_the_guarantee_runs_before_evidence_assembly(self):
        """Ordering matters: the evidence message is BUILT from `_tool_block`.
        Composing the dataset block after that append left it out of the
        prompt entirely — the model answered "I don't have the contents of the
        file" while the row sat in a variable (measured 2026-09-16)."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert src.index("THE DERIVATION LANE MUST NOT DEPEND") < src.index(
            "# Fresh tool results go LAST"), (
            "the dataset block is composed after the evidence message is "
            "assembled, so the model never sees it")

    def test_the_guarantee_is_idempotent_on_the_LANES_OWN_signature(self):
        """A block that already carries the matched row + its formulas is not
        re-probed — but a block that merely starts with DATASET CATALOG (the
        planner's own datasets.search output) must NOT count as present, or
        the guard suppresses the lane that produces the answer (measured
        2026-09-16: 12k chars of other sheets' rows, no matched row, and the
        model answered "I don't have the PRICE VIPUL document")."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert '"FORMULAS FOR THE MATCHED ROW" in _block_text' in src
        assert 'and "FORMULAS FOR THE MATCHED ROW" in _block_text' in src


class TestDerivationEvidenceFraming:
    """The evidence block must SAY what it is, or a model treats the decisive
    rows as background.

    Measured 2026-09-16 with byte-identical evidence: gpt-5-mini walked the
    formula chain (row 235, six formulas, unresolved O235) while
    deepseek-v4-flash answered "I don't have the contents of the PRICE VIPUL
    document — could you share it?" on three separate runs. The fix is framing,
    not a pinned model (which the brief forbids).
    """

    def _instruction(self, block: str) -> str:
        """Reproduce the message the orchestrator builds for a tool block."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "DERIVATION EVIDENCE" in src, "the framing is gone"
        assert 'if "FORMULAS FOR THE MATCHED ROW" in _tool_block' in src
        return src

    def test_framing_present_for_a_derivation_block(self):
        src = self._instruction("")
        # Phrases that appear inside a single source literal (the message is
        # built from concatenated strings, so a phrase spanning two literals
        # would not be found here).
        for phrase in ("DERIVATION EVIDENCE", "ARE the answer; you already have them",
                       "the SHEET, the ROW NUMBER", "is UNRESOLVED",
                       "ask the user to share or upload it",
                       "every value you need is in"):
            assert phrase in src, f"missing instruction: {phrase!r}"

    def test_framing_is_conditional_on_the_matched_row(self):
        """A mail-only block must not be labelled a derivation."""
        src = self._instruction("")
        assert '_evidence_instruction += "\\n" + _tool_block' in src


class TestDerivationRowUseGuard:
    """The matched row was DELIVERED; a reply that cites no row ignored it.

    Deterministic — it does not depend on how a model phrases its refusal.
    Measured 2026-09-16, byte-identical evidence: one model walked the chain
    while another said "the required live-data lookup failed" or asked which
    record the user meant. The wording-based inability guard catches only some
    of those; this catches the fact.
    """

    BLOCK = ("DATASET CATALOG — derivation inputs\n"
             "SQL RESULT from 'PRICE VIPUL (6).xlsx' sheet 'Sheet1'\n"
             "R235 | Product Name=F-52\"x16G | LIST Price=7519.0 | "
             "FORMULAS FOR THE MATCHED ROW(S): G235==F235*0.9")

    def test_reply_without_a_row_reference_is_flagged(self):
        assert co._derivation_reply_ignored_the_row(
            "I don't have the contents of the document — could you share it?",
            self.BLOCK) is True

    def test_reply_that_uses_the_row_is_not_flagged(self):
        assert co._derivation_reply_ignored_the_row(
            "Row 235 of Sheet1: G235 = F235 * 0.9 → 4815", self.BLOCK) is False
        assert co._derivation_reply_ignored_the_row(
            "R235 is the matched row; LIST Price = 7519", self.BLOCK) is False

    def test_no_derivation_evidence_means_no_verdict(self):
        assert co._derivation_reply_ignored_the_row(
            "whatever", "MAIL ONLY: - [ingested mailbox] foo") is False
        assert co._derivation_reply_ignored_the_row("whatever", None) is False

    def test_guard_regenerates_once_and_keeps_the_row_citing_reply(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "_derivation_reply_ignored_the_row(" in src
        assert "reply ignored the delivered" in src
        # ...and the regeneration only replaces the reply if it FIXED it.
        assert "_fixed and not _derivation_reply_ignored_the_row(" in src


class TestDerivationNotFlaggedAsFabrication:
    """A derivation EVALUATES its evidence; the check must not call that lying.

    Measured 2026-09-16 on a CORRECT chain:
      "[figure-grounding] reply states figures the evidence does not contain:
       5,625.30, 7,518, 1,893.70 — grounded regeneration"
    followed by a full regeneration (~60-90 s) AND
      "[LearningRouter] fabrication observed for openai/gpt-5-mini
       (question_answering): unsupported_figures"
    — a fabrication verdict recorded against the model that answered right.
    The figures are computed from the stored formulas (7518.44 = 6465.86/0.86)
    and can never appear verbatim in the evidence; flagging them makes every
    correct derivation look like a fabrication.
    """

    def test_guard_is_skipped_only_for_VERIFIED_claims(self):
        """Re-contracted 2026-09-16 (audit directive 3).

        The old shape skipped figure-grounding when the evidence carried a
        formula marker AND the reply contained ANY row citation — so an invented
        chain evaded verification by writing "row 235". A citation proves nothing
        about arithmetic. The skip is now keyed to the verification contract: an
        anchored claim that the workbook's own formulas REPRODUCE.
        """
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "verify_derivation_claims" in src
        assert "_derivation_contradicted" in src
        # the skip must not be reachable from a bare row citation
        assert "_ROW_CITE_RE.search(_content or" not in src
        assert "not _derivation_reply:" not in src

    def test_a_contradicted_derivation_is_never_treated_as_grounded(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "NOT skipped: the workbook contradicts" in src

    def test_a_failed_verifier_does_not_read_as_grounded(self):
        """A verifier that cannot run must report UNVERIFIED, never clean."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "treated as UNVERIFIED, not as grounded" in src

    def test_a_non_derivation_reply_is_still_checked(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        # The guard still runs for ordinary evidence-bearing replies.
        assert "_unsupported_figures(" in src


class TestCanvasEditLegIsBoundedForDerivations:
    """A derivation ask must not pay for a canvas-edit DECLINE.

    Measured 2026-09-16: that leg cost 40-69 s of a turn whose reply is 57-94 s
    against a ~120 s client budget, and it declines these asks anyway ("canvas
    edit declined: the turn needs live data and the lookup failed"). Bounding it
    at 12 s brought a complete, correct derivation turn to **84 s** with the
    full chain — under the 95 s turn budget for the first time.
    """

    def test_the_bound_exists_and_is_configurable(self):
        assert hasattr(co, "_CANVAS_EDIT_DERIVATION_WAIT_SECONDS")
        assert co._CANVAS_EDIT_DERIVATION_WAIT_SECONDS > 0
        import os

        assert os.getenv("ATOM_CANVAS_EDIT_DERIVATION_WAIT_SECONDS") is None or \
            float(os.getenv("ATOM_CANVAS_EDIT_DERIVATION_WAIT_SECONDS")) > 0

    def test_the_bound_applies_only_to_derivation_asks(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator.process_chat_message)
        assert "_CANVAS_EDIT_DERIVATION_WAIT_SECONDS" in src
        # A non-derivation ask still awaits the leg unbounded by this timeout.
        assert "else:\n                        _edit_response = await _edit_leg" in src

    def test_a_bounded_leg_falls_through_instead_of_failing(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator.process_chat_message)
        assert "canvas-edit leg bounded at" in src
        assert "_edit_response = None" in src


class TestDerivationTurnBudget:
    """The internal budget must not be STRICTER than the client it protects.

    Measured 2026-09-16: `http=200 108.6s delivery=structured_error
    (turn_budget_exceeded)` for a derivation that fits the client's ~120 s
    window. The 95 s default failed turns that were about to succeed.
    """

    def test_derivation_budget_is_longer_than_the_default(self):
        assert co.CHAT_DERIVATION_TURN_BUDGET_SECONDS > co.CHAT_TURN_BUDGET_DEFAULT_SECONDS

    def test_derivation_budget_stays_under_the_client_window(self):
        # The point is to fail BEFORE the client does, not after.
        assert co.CHAT_DERIVATION_TURN_BUDGET_SECONDS < 120.0

    def test_resolver_selects_by_request_class(self):
        assert co._chat_turn_budget_seconds(derivation=True) == \
            co.CHAT_DERIVATION_TURN_BUDGET_SECONDS
        assert co._chat_turn_budget_seconds() == co.CHAT_TURN_BUDGET_DEFAULT_SECONDS

    def test_env_override_wins_for_each_class(self, monkeypatch):
        monkeypatch.setenv("ATOM_DERIVATION_TURN_BUDGET_SECONDS", "77")
        assert co._chat_turn_budget_seconds(derivation=True) == 77.0
        monkeypatch.setenv("ATOM_CHAT_TURN_BUDGET_SECONDS", "55")
        assert co._chat_turn_budget_seconds() == 55.0

    def test_invalid_env_falls_back_without_raising(self, monkeypatch):
        monkeypatch.setenv("ATOM_DERIVATION_TURN_BUDGET_SECONDS", "soon")
        assert co._chat_turn_budget_seconds(derivation=True) == \
            co.CHAT_DERIVATION_TURN_BUDGET_SECONDS


class TestFirstVisibleDeadlineOnEveryChunk:
    """A stream that emits hidden reasoning forever never times out.

    The slice-timeout branch bounds a stream that goes SILENT; it does not bound
    one that keeps sending non-visible chunks (reasoning deltas) inside the
    slice. Measured 2026-09-16 on one build: a derivation turn with
    `reply STREAMED: 9.9s (445 chunks)` finished in ~35 s, while a
    hidden-reasoning stream took 185-209 s for the same answer — the difference
    is paying the stream's full duration AND then a non-streaming regeneration.
    """

    def test_deadline_is_checked_at_the_top_of_every_iteration(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        loop = src[src.index("while True:"):]
        loop = loop[:loop.index("try:")]
        assert "_first_visible_limit" in loop, (
            "the first-visible deadline is not checked before awaiting the "
            "next chunk, so a continuously-streaming hidden-reasoning reply "
            "is unbounded")
        assert "not _buf" in loop

    def test_the_bound_still_yields_to_a_visible_reply(self):
        """Once content has arrived the deadline must never fire."""
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "if (not _buf and _first_visible_limit > 0" in src

    def test_a_derivation_gets_the_tighter_deadline(self):
        """A derivation answer is a short transcription; 30 s of silence is a
        route spending the turn on hidden thinking (measured 2026-09-16: the
        zero-visible stream plus a starved fallback ended the only case that
        was never evaluated, at 141.5 s)."""
        assert co._DERIVATION_STREAM_FIRST_VISIBLE_SECONDS < \
            co._STREAM_FIRST_VISIBLE_SECONDS
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert "_first_visible_limit = _first_visible_limit_seconds(" in src
        assert "_is_derivation_ask)" in src


class TestDerivationCompletionCap:
    """`max_tokens` also sets the HIDDEN-reasoning budget.

    The reasoning body grants a third of the completion cap, so an
    over-generous cap lets a reasoning-heavy route think ~2000 tokens and then
    truncate (`finish_reason=length`) with nothing visible — the second half of
    the 2026-09-16 derivation failure ("openrouter/openai/gpt-5-mini returned no
    visible content (finish_reason=length)"). A derivation reply is a few
    hundred tokens, so a 3000 cap bounds the thinking without shortening the
    answer.
    """

    def test_the_cap_is_derivation_scoped_and_bounded(self):
        from core.llm.byok_handler import _DEFAULT_COMPLETION_MAX_TOKENS

        assert co._DERIVATION_COMPLETION_MAX_TOKENS < _DEFAULT_COMPLETION_MAX_TOKENS
        assert co._DERIVATION_COMPLETION_MAX_TOKENS > 1024, (
            "below the reasoning floor the provider gets no bounded-thinking "
            "field at all")

    def test_every_reply_leg_call_carries_it(self):
        import inspect

        src = inspect.getsource(co.ChatOrchestrator._get_qwen_response)
        assert 'extra_kwargs["max_tokens"] = _reply_max_tokens' in src
        assert "max_tokens=_reply_max_tokens" in src, (
            "the streaming call must use the derivation cap too")
        assert "_DERIVATION_COMPLETION_MAX_TOKENS" in src

    def test_env_override_applies_without_a_restart(self, monkeypatch):
        """Both levers resolve per call, like the turn budget does — so an
        operator can change them without restarting the serving process."""
        assert co._reply_token_cap(True) == co._DERIVATION_COMPLETION_MAX_TOKENS
        assert co._first_visible_limit_seconds(True) == \
            co._DERIVATION_STREAM_FIRST_VISIBLE_SECONDS
        monkeypatch.setenv("ATOM_DERIVATION_COMPLETION_MAX_TOKENS", "2500")
        monkeypatch.setenv("ATOM_DERIVATION_STREAM_FIRST_VISIBLE_SECONDS", "9")
        assert co._reply_token_cap(True) == 2500
        assert co._first_visible_limit_seconds(True) == 9.0
        # ...and the ordinary path is untouched by the derivation knobs.
        monkeypatch.setenv("ATOM_DERIVATION_COMPLETION_MAX_TOKENS", "1")
        from core.llm.byok_handler import _DEFAULT_COMPLETION_MAX_TOKENS

        assert co._reply_token_cap(False) == _DEFAULT_COMPLETION_MAX_TOKENS

    def test_invalid_values_fall_back_without_raising(self, monkeypatch):
        monkeypatch.setenv("ATOM_DERIVATION_COMPLETION_MAX_TOKENS", "soon")
        monkeypatch.setenv("ATOM_DERIVATION_STREAM_FIRST_VISIBLE_SECONDS", "")
        assert co._reply_token_cap(True) == co._DERIVATION_COMPLETION_MAX_TOKENS
        assert co._first_visible_limit_seconds(True) == \
            co._DERIVATION_STREAM_FIRST_VISIBLE_SECONDS
