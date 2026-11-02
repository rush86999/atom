"""MEM-07: a tool failure queues a PENDING candidate, never a code change."""
from __future__ import annotations

import asyncio

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from core.agent_evolution_candidates import capture_tool_failure
from core.models import HITLAction, HITLActionStatus


def _world():
    engine = sa.create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=sa.pool.StaticPool,
    )
    HITLAction.__table__.create(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def test_capture_is_pending_and_idempotent(monkeypatch):
    engine, factory = _world()
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setenv("ATOM_AGENT_EVOLUTION_ENABLED", "true")
    try:
        first = capture_tool_failure(
            agent_id="agent-1", tool_name="crm.search_records",
            error="provider returned 500")
        repeat = capture_tool_failure(
            agent_id="agent-1", tool_name="crm.search_records",
            error="provider returned 500")
        other = capture_tool_failure(
            agent_id="agent-1", tool_name="crm.search_records",
            error="provider returned 401")
        assert first and first == repeat
        assert other and other != first

        db = factory()
        try:
            rows = db.query(HITLAction).all()
            assert len(rows) == 2
            assert {row.status for row in rows} == {
                HITLActionStatus.PENDING.value}
            assert {row.action_type for row in rows} == {
                "agent_evolution_candidate"}
            assert {row.platform for row in rows} == {"agent_evolution"}
            assert all(
                "no code or configuration change is applied"
                in (row.params or {}).get("proposed_scope", "")
                for row in rows)
        finally:
            db.close()
    finally:
        engine.dispose()


def test_capture_is_off_without_the_flag(monkeypatch):
    engine, factory = _world()
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.delenv("ATOM_AGENT_EVOLUTION_ENABLED", raising=False)
    try:
        assert capture_tool_failure(
            agent_id="agent-1", tool_name="crm.search_records",
            error="boom") is None
        db = factory()
        try:
            assert db.query(HITLAction).count() == 0
        finally:
            db.close()
    finally:
        engine.dispose()


def test_tool_wrapper_captures_a_failed_custom_action(monkeypatch):
    engine, factory = _world()
    monkeypatch.setattr("core.database.get_db_session", factory)
    monkeypatch.setenv("ATOM_AGENT_EVOLUTION_ENABLED", "true")

    def boom(_args, _context):
        raise RuntimeError("tool exploded")

    from core.generic_agent import GenericAgent

    agent = object.__new__(GenericAgent)
    agent.id = "agent-1"
    agent._custom_actions = {"boom": boom}
    try:
        result = asyncio.run(agent._step_act("boom", {}))
        assert "Error" in result
        db = factory()
        try:
            rows = db.query(HITLAction).all()
            assert len(rows) == 1
            assert rows[0].status == HITLActionStatus.PENDING.value
            assert "tool exploded" in rows[0].params["error"]
        finally:
            db.close()
    finally:
        engine.dispose()
