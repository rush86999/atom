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
