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
