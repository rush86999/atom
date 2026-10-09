# -*- coding: utf-8 -*-
"""B's calculation grounding — the narration/record boundary (pv-B).

Captured failure (pv-B-ac55c): the ask "9 hours, $120 in materials"
bound hours=9/rate=150 but the engine returned "materials: INPUT
NEEDED", so NO durable engine operation recorded — and the reply still
narrated "$1,470 … taught formula" (a money figure with teaching
authority, a soft flag that is not a disclosure). Arithmetic-correct,
not calculation-certified.

These pins hold the WIRING, not just the detector: a calc-bound turn
whose reply is pv-B-shaped and has NO engine record meets the
production replacement condition (the reply must be replaced, not
served); the same figure WITH the engine's record supplies
_calc_evidence (the record licenses the figure). The input-binding
contract itself is pinned in test_calculate_toolplan_boundary.py; this
file never duplicates it.

Scratch in-memory DB + the REAL teaching. Never the live DB.
"""
from __future__ import annotations

import asyncio
import os
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, User

PVB_ASK = ("Estimate this service job using our taught rates: "
           "9 hours, $120 in materials.")

# The captured pv-B reply shape: a money figure WITH teaching/formula
# authority and WITHOUT an honest not-computed disclosure (the soft
# "transparency" flag is not a disclosure phrase).
PVB_REPLY = (
    "Using the taught formula Service estimate: ROUNDUP(hours * rate "
    "+ materials, 0):\n\n9 \u00d7 150 = 1,350 \u2192 1,350 + 120 = "
    "1,470 \u2192 estimated service job: $1,470\n\nOne flag for "
    "transparency: the calculator run on my side bound hours = 9 and "
    "rate = 150 but returned \u201cmaterials: INPUT NEEDED\u201d "
    "\u2014 it did not independently bind the $120. So the $1,470 "
    "follows from applying the taught formula to the materials "
    "figure you supplied.")

LESSON_RATE_150 = {
    "id": "1451b758f7964e1a9d1878704b7ce054",
    "source": "teacher", "teacher_agent_id": "human_supervisor",
    "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "learned_at": "2026-10-06T13:22:44.344495+00:00", "scope": "global",
}

_STATE = {}


@pytest.fixture()
def world():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def scratch():
        s = factory()
        try:
            yield s
            s.commit()
        finally:
            s.close()

    import core.database as dbmod
    old = dbmod.get_db_session
    dbmod.get_db_session = scratch
    with scratch() as db:
        db.add(User(id="u-pvb", email="pvb-ground@example.com",
                    first_name="P", last_name="V", role="user",
                    status="active"))
        db.add(AgentRegistry(
            id="pvb-ground-agent", name="pvb", status="active",
            category="trainee", module_path="agents.pvb",
            class_name="PvbAgent",
            configuration={"learning": {"log": [LESSON_RATE_150]}}))
    _STATE["factory"] = factory
    yield {"user": "u-pvb", "ws": "default"}
    dbmod.get_db_session = old
    engine.dispose()


def test_pvb_shaped_reply_without_record_meets_replacement(world):
    """The captured pv-B turn state: a calc-bound ask, a pv-B-shaped
    reply, and NO engine record. Every predicate of the production
    replacement condition holds — the reply must be replaced with the
    honest not-computed wording, never served as engine-computed."""
    from integrations.chat_orchestrator import (
        _calc_bound_turn,
        _reply_claims_unrecorded_teaching_figure,
    )
    from core.pricing_calculation import _calc_narration_allowance

    allowance = _calc_narration_allowance(None)
    assert allowance == {}, "no engine record -> no narration authority"
    assert _calc_bound_turn(PVB_ASK, "conv-pvb-1", "default") is True, (
        "the pv-B ask is bound to the calculation contract")
    assert _reply_claims_unrecorded_teaching_figure(PVB_REPLY) is True, (
        "the pv-B reply shape (money figure + taught authority, no "
        "disclosure) must be flagged")
    # The production wiring's exact condition (chat_orchestrator's
    # calc-wording rule): no evidence + content + message + bound turn
    # + flagged reply -> replace. If any predicate regresses, the
    # pv-B escape reopens.
    assert (not allowance and PVB_REPLY and PVB_ASK
            and _calc_bound_turn(PVB_ASK, "conv-pvb-1", "default")
            and _reply_claims_unrecorded_teaching_figure(PVB_REPLY)), (
        "the replacement condition must hold for the captured pv-B state")


def test_engine_record_supplies_calc_evidence_for_the_same_figure(world):
    """With the engine's record, the same $1,470 IS engine-backed: the
    tool block carries the operation reference, the allowance resolves
    the record with the figure in its allowed set, and the replacement
    branch is not taken. Narration may cite an engine computation ONLY
    through this record."""
    from core.chat_tool_planner import ToolPlan, execute_tool_plan
    from core.pricing_calculation import _calc_narration_allowance

    async def _run():
        plan = ToolPlan(use_tool=True,
                        service="datasets.calculate", query=PVB_ASK)
        return await execute_tool_plan(
            plan, "u-pvb", tenant_id="default",
            context={"conversation_id": "conv-pvb-2",
                     "workspace_id": "default"})

    block = asyncio.run(_run())
    assert block and "[calc:result_id=" in block, (
        "the engine run must publish its operation reference on the block")
    allowance = _calc_narration_allowance(
        block, expected_conversation_id="conv-pvb-2",
        expected_user_id="u-pvb")
    assert allowance.get("records"), (
        "the allowance must resolve the current request's record")
    assert "1470" in (allowance.get("allowed_figures") or []), (
        "the computed figure must be in the record's allowed set")
    # _calc_evidence is truthy exactly when records resolve — the
    # production wiring's replacement branch is not taken.
    assert allowance is not None
