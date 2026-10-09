# -*- coding: utf-8 -*-
"""Owner check B (2026-10-09): a COMPLETED, durably recorded
calculation whose narration fails — the computed result and the
operation identity survive unchanged.

Path-level pin through the production pieces: the real calculate lane
(execute_tool_plan — engine run, durable operation, grounded block),
then the production delivery function the orchestrator invokes on
narration failure (_deterministic_calc_fallback over the record-derived
allowance). The full integrated path (planner down, providers
exhausted, deterministic render shipped through the live chat route) is
separately evidenced in
backend/data/acceptance_worlds/brennan_practical_value_report_20261009.json
(session pv-B3-94432: "$1,100 … engine-computed, exact" served during a
total provider outage) and is deliberately not re-staged here: the
orchestrator's intent/narration routing under injected LLM stubs diverts
to the legacy lane, so a full-turn stub test would pin the stub, not the
system.

Scratch in-memory DB + the REAL teaching. Never the live DB.
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import AgentRegistry, Base, TaskOperationRecord, User

LESSON_RATE_150 = {
    "id": "1451b758f7964e1a9d1878704b7ce054",
    "source": "teacher", "teacher_agent_id": "human_supervisor",
    "topic": "service estimates",
    "lesson": ("Service estimate: estimate = ROUNDUP(hours * rate + "
               "materials, 0). Our service rate is 150 per hour."),
    "learned_at": "2026-10-06T13:22:44.344495+00:00", "scope": "global",
}

MSG = ("Estimate this service job using our taught rates: "
       "8 hours, $60 in materials.")


@pytest.fixture()
def world():
    engine = create_engine("sqlite://",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    from contextlib import contextmanager

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
        db.add(User(id="u-survive", email="survive@example.com",
                    first_name="S", last_name="T", role="user",
                    status="active"))
        db.add(AgentRegistry(
            id="survive-agent", name="survive agent", status="active",
            category="trainee", module_path="agents.survive",
            class_name="SurviveAgent",
            configuration={"learning": {"log": [LESSON_RATE_150]}}))
    yield factory
    dbmod.get_db_session = old
    engine.dispose()


def test_completed_calc_result_and_identity_survive_narration_failure(
        world):
    from core.chat_tool_planner import ToolPlan, execute_tool_plan
    from core.pricing_calculation import _calc_narration_allowance
    from integrations.chat_orchestrator import _deterministic_calc_fallback

    # 1. the engine COMPLETES and records durably (production lane)
    block = asyncio.run(execute_tool_plan(
        ToolPlan(use_tool=True, service="datasets", intent="calculate",
                 query=MSG),
        "u-survive", tenant_id="default",
        context={"conversation_id": "conv-survive-1",
                 "workspace_id": "default"}))
    assert block and "engine-computed" in block
    assert "1260" in block.replace(",", ""), block[:400]

    # 2. narration fails: the delivery guard resolves the allowance from
    # THIS block and renders deterministically — no model call
    allowance = _calc_narration_allowance(
        block, expected_conversation_id="conv-survive-1",
        expected_user_id="u-survive")
    assert allowance.get("records"), (
        "the recorded operation must license the figure")
    rendered = _deterministic_calc_fallback(allowance, [])
    assert rendered, "the deterministic render must ship the result"
    assert "1260" in rendered.replace(",", "")
    assert "taught-expression:Service estimate" in rendered, (
        "the operation's policy identity must survive in the delivery")

    # 3. exactly ONE durable operation, unchanged by the delivery
    with world() as db:
        ops = (db.query(TaskOperationRecord)
               .filter(TaskOperationRecord.operation_type == "calculate")
               .all())
        assert len(ops) == 1, f"expected one calculate op, got {len(ops)}"
        identity = ops[0].idempotency_key

    # 4. re-delivery is stable — the identity never changes
    rendered_again = _deterministic_calc_fallback(allowance, [])
    assert "1260" in rendered_again.replace(",", "")
    with world() as db:
        ops_after = (db.query(TaskOperationRecord)
                     .filter(TaskOperationRecord.operation_type == "calculate")
                     .all())
        assert len(ops_after) == 1
        assert ops_after[0].idempotency_key == identity, (
            "the operation identity must be unchanged")
