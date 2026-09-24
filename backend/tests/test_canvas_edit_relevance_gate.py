"""The canvas-edit evidence leg must not execute an off-request plan.

RCA 2026-09-17 finding 2: this leg (source canvas_edit_fresh_data) ran the
PREVIOUS turn's "PRICE VIPUL price list attachment" mailbox search on the
scorecard turn, and the block was then reused by the reply. Pins: an
irrelevant plan is declined BEFORE execution (and never written to the
blackboard block), a relevant plan executes as before, and the
existing-block reuse path is untouched.

Separate module because test_chat_canvas_editor.py installs an autouse
fixture that mocks fetch_fresh_data_section for that whole file.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core.chat_canvas_editor as ed

SCORECARD_ASK = (
    "search for the vendor scorecard and check the reliability 0.87, then "
    "update the workbook"
)
STALE_QUERY = "PRICE VIPUL price list attachment"


@pytest.mark.asyncio
async def test_off_request_plan_declines_before_execution(monkeypatch):
    """The RCA shape: the plan answers the OLD ask — it must decline
    (needed/ok = True/False) and the lookup must never run."""
    called = {"exec": 0}

    async def plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search", query=STALE_QUERY)

    async def spy_lookup(*args, **kwargs):
        called["exec"] += 1
        return "PRICE VIPUL mailbox rows"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        spy_lookup)

    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(plan()),
    )
    assert (res.needed, res.ok) == (True, False)
    assert res.block == ""
    assert called["exec"] == 0


@pytest.mark.asyncio
async def test_relevant_plan_still_executes(monkeypatch):
    async def plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search",
                               query="vendor scorecard reliability 0.87")

    async def fast_lookup(*args, **kwargs):
        return "vendor scorecard rows"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        fast_lookup)

    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(plan()),
    )
    assert res.needed is True
    assert res.ok is True
    assert "vendor scorecard rows" in res.block


@pytest.mark.asyncio
async def test_existing_block_reuse_is_not_gated(monkeypatch):
    """Reuse of an already-executed block is the point of the blackboard;
    the gate lives at plan acceptance, not here."""
    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        existing_block="LIVE TOOL RESULTS: vendor scorecard rows",
    )
    assert res.needed is True
    assert res.ok is True
    assert "vendor scorecard rows" in res.section


@pytest.mark.asyncio
async def test_missing_query_fails_open(monkeypatch):
    """A plan without a query (kwargs-carried target) must not decline."""
    async def plan():
        return SimpleNamespace(use_tool=True, service="documents",
                               intent="read", query=None)

    async def fast_lookup(*args, **kwargs):
        return "document text"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        fast_lookup)

    res = await ed.fetch_fresh_data_section(
        "open the scorecard workbook", [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(plan()),
    )
    assert res.needed is True
    assert res.ok is True


# --- R4 stamp consumption, pinned 2026-09-17 (ZCode): the planner stamps
# the verdict of record at acceptance; this gate must CONSUME it instead of
# re-running the raw lexical verdict and re-declining a provenance-verified
# lookup. ---

BODY_ASK = "search for this one: $ 5,350.00 - 10 % in stock, then update the draft"


@pytest.mark.asyncio
async def test_provenance_stamped_plan_is_not_redeclined(monkeypatch):
    """The recorded R4 leftover: query = thread SUBJECT ('FW: RFQ - Foot
    shear'), message = pasted BODY ('$ 5,350.00') — zero lexical overlap by
    construction, raw verdict irrelevant. The planner validated it by
    provenance and stamped it; the gate honors the stamp and executes."""
    executed = {"n": 0}

    async def plan():
        return SimpleNamespace(use_tool=True, service="memory",
                               intent="search", query="FW: RFQ - Foot shear",
                               relevance_verdict="relevant",
                               relevance_basis="provenance-quote")

    async def spy_lookup(*args, **kwargs):
        executed["n"] += 1
        return "RFQ foot shear message text"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        spy_lookup)

    res = await ed.fetch_fresh_data_section(
        BODY_ASK, [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(plan()),
    )
    assert res.needed is True
    assert res.ok is True
    assert executed["n"] == 1


@pytest.mark.asyncio
async def test_stamped_irrelevant_still_declines(monkeypatch):
    """The stamp cuts both ways: a plan the planner shipped stamped
    irrelevant (repair failed) is still declined before execution — the
    stamp must never become a blanket bypass."""
    called = {"exec": 0}

    async def plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search", query=STALE_QUERY,
                               relevance_verdict="irrelevant",
                               relevance_basis="no-overlap")

    async def spy_lookup(*args, **kwargs):
        called["exec"] += 1
        return "should never run"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        spy_lookup)

    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        plan_task=asyncio.create_task(plan()),
    )
    assert (res.needed, res.ok) == (True, False)
    assert called["exec"] == 0


# --- 2026-09-23 AUDIT (canvas 0e4defa5): an "irrelevant" verdict — stamped
# or raw — no longer declines on its own. It is re-judged against the
# conversation history and the open canvas's subject before the gate
# declines, because a canvas-edit evidence query names the CANVAS's subject
# ("update with actual prices in the email" shares zero words with the
# correct mailbox query for the products being priced). ---

UPDATE_ASK = (
    "update with actual prices in the email. if unable, say so and why. "
    "square brackets with reference labels will not work in an email sent "
    "to a lead"
)
EVIDENCE_QUERY = (
    "Chandrakant amacisaac alternatives roll bender bead roller flanger "
    "slitter TK 16"
)
QUOTE_CANVAS = {
    "canvas_id": "0e4defa5-a0f3-4e56-b8a7-976c0a93d4fb",
    "canvas_type": "email",
    "title": "Quote – Roper Whitney Roll Bender, Linmac Bead Roller, "
             "Manual Flanger & Slitters",
    "content": {"body": "<table><tr><td>Roper Whitney Roll Bender</td>"
                        "<td>TBD</td></tr></table>"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("stamp", [None, "irrelevant"],
                         ids=["no-stamp", "stamped-irrelevant"])
async def test_update_prices_evidence_query_executes_via_canvas_target(
        monkeypatch, stamp):
    """THE live incident: the edit instruction names the artifact ('the
    email') and the fields ('actual prices'); the evidence query names the
    quoted products. With the open canvas in scope the gate must let the
    lookup run — whether the planner stamped the verdict or not."""
    executed = {"n": 0}

    def plan_ns():
        ns = SimpleNamespace(use_tool=True, service="outlook",
                             intent="search", query=EVIDENCE_QUERY)
        if stamp is not None:
            ns.relevance_verdict = stamp
            ns.relevance_basis = "zero-overlap"
        return ns

    async def plan():
        return plan_ns()

    async def spy_lookup(*args, **kwargs):
        executed["n"] += 1
        return "Chandrakant's Sept 18 quote rows"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        spy_lookup)

    res = await ed.fetch_fresh_data_section(
        UPDATE_ASK, [], MagicMock(), "user-1",
        canvas=QUOTE_CANVAS,
        plan_task=asyncio.create_task(plan()),
    )
    assert executed["n"] == 1
    assert res.needed is True
    assert res.ok is True
    assert "Chandrakant's Sept 18 quote rows" in res.block
    assert res.declined_irrelevant is False


@pytest.mark.asyncio
async def test_stale_query_still_declines_with_unrelated_canvas(monkeypatch):
    """Defense-in-depth intact: the previous ask's query shares nothing
    with the scorecard canvas either — the gate still declines BEFORE
    execution, as a RELEVANCE rejection (distinct from retrieval
    failure)."""
    executed = {"n": 0}

    async def plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search", query=STALE_QUERY)

    async def spy_lookup(*args, **kwargs):
        executed["n"] += 1
        return "PRICE VIPUL mailbox rows"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan",
                        spy_lookup)

    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        canvas={"canvas_id": "cv", "canvas_type": "spreadsheet",
                "title": "Vendor Scorecard Q3",
                "content": {"content": "vendor reliability scorecard"}},
        plan_task=asyncio.create_task(plan()),
    )
    assert executed["n"] == 0
    assert (res.needed, res.ok) == (True, False)
    assert res.declined_irrelevant is True


@pytest.mark.asyncio
async def test_canvas_target_does_not_rescue_an_unrelated_edit_request(monkeypatch):
    executed = {"n": 0}

    async def plan():
        return SimpleNamespace(use_tool=True, service="outlook",
                               intent="search",
                               query="roll bender alternatives")

    async def spy_lookup(*args, **kwargs):
        executed["n"] += 1
        return "unrelated quote rows"

    monkeypatch.setattr("core.chat_tool_planner.execute_tool_plan", spy_lookup)

    res = await ed.fetch_fresh_data_section(
        SCORECARD_ASK, [], MagicMock(), "user-1",
        canvas=QUOTE_CANVAS,
        plan_task=asyncio.create_task(plan()),
        allow_canvas_target=False,
    )
    assert executed["n"] == 0
    assert (res.needed, res.ok) == (True, False)
    assert res.declined_irrelevant is True
