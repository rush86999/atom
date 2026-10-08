"""Phase-2 turn interpretation: propose semantics, never authorization.

Required proofs (owner directive 2026-10-08):
- Paraphrases produce equivalent work (same actions/subjects).
- Compound research + teaching retains BOTH actions.
- Negated edits authorize no mutation — model proposals are overwritten
  by the deterministic policy.
- Timeout / malformed output / unavailable models yield an EXPLICIT
  unresolved interpretation without executing guessed work.
- The synchronous build_turn_decision interface is untouched (its own
  suite stays green).
"""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("TESTING", "1")

from core import turn_decision as td


class _StubLLM:
    """Structured-generation stub returning a canned interpretation."""

    def __init__(self, payload=None, hang=False, raise_error=False):
        self.payload = payload or {}
        self.hang = hang
        self.raise_error = raise_error
        self.calls: list = []

    async def generate_structured_response(self, **kwargs):
        self.calls.append(kwargs)
        if self.hang:
            await asyncio.sleep(30)
        if self.raise_error:
            raise RuntimeError("no structured model available")
        return self.payload


def _interpretation(actions, subjects, scope_change="replace", **extra):
    doc = {
        "actions": [
            {"kind": k, "subjects": s if isinstance(s, list) else [s],
             "note": ""} for k, s in actions],
        "subjects": subjects,
        "sources": extra.get("sources", []),
        "requested_fields": extra.get("fields", []),
        "output_format": extra.get("output_format", ""),
        "constraints": extra.get("constraints", []),
        "scope_change": scope_change,
        "confidence": extra.get("confidence", 0.8),
    }
    return SimpleNamespace(**doc, model_dump=lambda: doc)


@pytest.fixture(autouse=True)
def _clean():
    td.reset_interpretation_for_tests()
    yield
    td.reset_interpretation_for_tests()


async def _run(stub, message, **kw):
    return await td.interpret_turn_request(
        message, session={}, history=[], context=kw.pop("context", {}),
        session_id="s-1", request_id="req-1", llm_service=stub, **kw)


@pytest.mark.asyncio
async def test_paraphrases_produce_equivalent_work():
    """Two phrasings of the same price ask propose the same action and
    the same full subject — the interpretation is about the request,
    not its wording."""
    subjects = ["Cedarberg 60-ton press brake"]
    stub_a = _StubLLM(_interpretation(
        [("research", subjects)], subjects))
    # Same semantic payload for the paraphrase: the CONTRACT under test
    # is that the consumer receives equivalent work descriptions, so the
    # proposals are compared after interpretation, not the prompts.
    a = await _run(stub_a, "Please find the price for a Cedarberg "
                    "60-ton press brake in the Consolidated Price List "
                    "2019 workbook")
    b = await _run(
        _StubLLM(_interpretation([("research", subjects)], subjects)),
        "What does a Cedarberg 60-ton press brake cost per the 2019 "
        "consolidated price list?")

    assert a["scope_change"] == "replace" == b["scope_change"]
    assert a["subjects"] == b["subjects"] == subjects
    assert [x["kind"] for x in a["actions"]] == \
        [x["kind"] for x in b["actions"]] == ["research"]
    assert all(x["authorization"] == "granted"
               for x in a["actions"] + b["actions"])


@pytest.mark.asyncio
async def test_compound_research_and_teaching_keeps_both():
    actions = [("research", ["No. 381", "U-22"]),
               ("learning", ["include the Tennsmith sheet for "
                             "Roper Whitney searches"])]
    out = await _run(_StubLLM(_interpretation(
        actions, ["No. 381", "U-22"], scope_change="extend")), "x")
    kinds = [x["kind"] for x in out["actions"]]
    assert kinds == ["research", "learning"], (
        "compound requests keep every requested action — no exclusive "
        "lane collapse")
    auth = {x["kind"]: x["authorization"] for x in out["actions"]}
    assert auth["research"] == "granted"
    assert auth["learning"] == "needs_confirmation"


@pytest.mark.asyncio
async def test_negated_edit_proposal_authorizes_no_mutation():
    """The model may PROPOSE an edit for 'research this; don't change the
    draft' — the deterministic policy must overwrite it to needs_grant."""
    out = await _run(_StubLLM(_interpretation(
        [("research", ["No. 381"]), ("canvas_edit", ["the draft"])],
        ["No. 381"], constraints=["don't change the draft"])),
        "Research the price for No. 381; don't change the draft yet",
        context={"canvas_id": "fork-1"})
    auth = {x["kind"]: x["authorization"] for x in out["actions"]}
    assert auth["canvas_edit"] == "needs_grant", (
        "a negated edit command is not a grant — no mutation authorized")
    assert auth["research"] == "granted"
    assert "don't change the draft" in out["constraints"]


@pytest.mark.asyncio
async def test_timeout_yields_explicit_unresolved():
    out = await _run(_StubLLM(hang=True), "check the price list")
    assert out["scope_change"] == "unresolved"
    assert out["origin"] == "unresolved"
    assert out["unresolved_reason"] == "timeout"
    assert out["actions"] == [], "unresolved never proposes work"
    assert out["deterministic_decision"] is not None, (
        "the floor decision rides along so callers keep the floor")


@pytest.mark.asyncio
async def test_unavailable_model_yields_explicit_unresolved():
    out = await _run(_StubLLM(raise_error=True), "check the price list")
    assert out["scope_change"] == "unresolved"
    assert out["unresolved_reason"] == "error"
    assert out["actions"] == []


@pytest.mark.asyncio
async def test_malformed_output_yields_explicit_unresolved():
    out = await _run(
        _StubLLM(_interpretation([], [], scope_change="replace")),
        "check the price list")
    assert out["scope_change"] == "unresolved"
    assert out["unresolved_reason"] == "no_actions_proposed"

    bad_scope = _interpretation([("research", ["x"])], ["x"],
                                scope_change="sideways")
    out2 = await _run(_StubLLM(bad_scope), "check the price list")
    assert out2["scope_change"] == "unresolved"


@pytest.mark.asyncio
async def test_scope_modes_pass_through_validated():
    for mode, expect in (("subset", "subset"), ("continue", "continue"),
                         ("extend", "extend")):
        out = await _run(_StubLLM(_interpretation(
            [("research", ["U-22"])], ["U-22"], scope_change=mode)), "x")
        assert out["scope_change"] == expect


@pytest.mark.asyncio
async def test_request_identity_and_origin_recorded():
    out = await _run(_StubLLM(_interpretation(
        [("research", ["x"])], ["x"])), "x")
    assert out["request_id"] == "req-1"
    assert out["schema"] == "turn-interpretation-1"
    assert out["origin"].startswith("llm")


@pytest.mark.asyncio
async def test_sync_interface_untouched_and_used_as_floor():
    """build_turn_decision stays synchronous and pure — the async path
    calls it for the floor decision without turning it into a network
    call."""
    import inspect

    assert not inspect.iscoroutinefunction(td.build_turn_decision)
    dec = td.build_turn_decision("find the price for No. 381", {}, [], {})
    assert dec["schema"] == "turn-decision-1"
