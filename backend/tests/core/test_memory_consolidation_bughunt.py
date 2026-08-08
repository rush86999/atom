# -*- coding: utf-8 -*-
"""Bug-hunt tests (TDD RED->GREEN) for core/memory_consolidation.py.

Each test targets a genuinely-new bug (fix absent from HEAD). The service
constructs its own SQLAlchemy session via ``SessionLocal()``, so we patch that
symbol to point at an in-memory SQLite session.
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import AgentMemory, AgentRegistry  # noqa: F401  (register models)
from core.memory_consolidation import MemoryConsolidationService


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_agent(db, agent_id="agent-1", tenant_id="t1"):
    agent = AgentRegistry(
        id=agent_id,
        name=agent_id,
        workspace_id="ws-1",
        tenant_id=tenant_id,
        category="Test",
        module_path="test",
        class_name="Test",
    )
    db.add(agent)
    db.commit()
    return agent


def _force_null_access_count(db, mem_id):
    """Force access_count to a real SQL NULL.

    The AgentMemory.access_count column has a Python-side ``default=0``, so an
    ORM insert of ``access_count=None`` is converted to 0 by SQLAlchemy before
    being flushed. On PostgreSQL, legacy/imported rows genuinely carry NULL, so
    to faithfully reproduce the production bug we bypass the ORM default with a
    core UPDATE that sets the column to NULL.
    """
    db.execute(
        AgentMemory.__table__.update()
        .where(AgentMemory.id == mem_id)
        .values(access_count=None)
    )
    db.commit()
    db.expire_all()


# ============================================================================
# BUG 1 (HIGH): update_importance_scores crashes (TypeError) when
# AgentMemory.access_count is None, and because the whole method is wrapped in
# a bare try/except that returns 0, the crash is SILENT — every importance
# update fails and the method reports "0 updated" with no error surfaced.
#
# The `access_count` column is nullable (no nullable=False on the model), and
# imported/legacy rows frequently have NULL access_count. The line
# `access_boost = min(0.3, memory.access_count * 0.01)` does
# `None * 0.01` -> TypeError.
# ============================================================================


class TestUpdateImportanceScoresNullAccessCount:
    """BUG: NULL access_count must be treated as 0, not crash the whole pass."""

    def test_null_access_count_does_not_crash(self, db):
        """BUG: a memory with access_count=NULL must not raise/short-circuit."""
        _make_agent(db)
        mem = AgentMemory(
            id="m1",
            agent_id="agent-1",
            workspace_id="ws-1",
            tenant_id="t1",
            content="hello",
            importance_score=0.5,
            access_count=0,  # placeholder; forced to NULL below
            last_accessed_at=datetime.now(timezone.utc),
        )
        db.add(mem)
        db.commit()
        _force_null_access_count(db, "m1")  # <-- the real production bug trigger

        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        # update_importance_scores() calls SessionLocal() AND db.close() in its
        # finally, so patch with a sessionmaker bound to the same engine; each
        # call yields a fresh session that shares the in-memory database.
        session_factory = sessionmaker(bind=db.bind)
        with patch("core.memory_consolidation.SessionLocal", side_effect=session_factory):
            updated = svc.update_importance_scores("t1")

        # Must run to completion (not silently return 0 via the except branch).
        # The memory was recently accessed -> recency boost -> score changes
        # -> it should be counted as updated.
        assert updated >= 1, (
            "update_importance_scores returned %d — it crashed on NULL "
            "access_count and was silently swallowed by the bare except" % updated
        )
        # Re-query on the test's own (still-open) session to read the committed
        # score; the service's internal session was closed in its finally block.
        refreshed = db.query(AgentMemory).filter(AgentMemory.id == "m1").first()
        # NULL access_count must be treated as 0 accesses (no access boost),
        # not crash. Final score = 0.5 base + 0.2 recency = 0.7 (clamped).
        assert refreshed.importance_score == pytest.approx(0.7, abs=1e-6)

    def test_null_access_count_then_normal_memory_both_updated(self, db):
        """BUG: a NULL-access_count memory must not abort processing of later rows."""
        _make_agent(db)
        bad_mem = AgentMemory(
            id="m-bad",
            agent_id="agent-1",
            workspace_id="ws-1",
            tenant_id="t1",
            content="bad",
            importance_score=0.5,
            access_count=0,  # placeholder; forced to NULL below
        )
        good_mem = AgentMemory(
            id="m-good",
            agent_id="agent-1",
            workspace_id="ws-1",
            tenant_id="t1",
            content="good",
            importance_score=0.5,
            access_count=10,  # access boost 0.1
            last_accessed_at=datetime.now(timezone.utc),  # recency boost 0.2
        )
        db.add_all([bad_mem, good_mem])
        db.commit()
        _force_null_access_count(db, "m-bad")  # would crash before the fix

        svc = MemoryConsolidationService(workspace_id="ws-1", tenant_id="t1")
        session_factory = sessionmaker(bind=db.bind)
        with patch("core.memory_consolidation.SessionLocal", side_effect=session_factory):
            updated = svc.update_importance_scores("t1")

        # The NULL-access_count memory must NOT abort the loop. good_mem is
        # processed regardless of query ordering and its score changes
        # (0.5 base + 0.1 access + 0.2 recency = 0.8), so `updated >= 1`.
        # Pre-fix, the loop crashed on bad_mem and returned 0 with good_mem
        # never visited.
        assert updated >= 1, (
            "expected good_mem to be updated, got %d (NULL access_count aborted "
            "the pass before reaching good_mem)" % updated
        )
        refreshed_good = db.query(AgentMemory).filter(AgentMemory.id == "m-good").first()
        # 0.5 base + min(0.3, 10*0.01)=0.1 access + 0.2 recency = 0.8
        assert refreshed_good.importance_score == pytest.approx(0.8, abs=1e-6)
        # bad_mem had no last_accessed_at and NULL access_count -> computed
        # score stays 0.5 == existing -> not counted as updated, and unchanged.
        refreshed_bad = db.query(AgentMemory).filter(AgentMemory.id == "m-bad").first()
        assert refreshed_bad.importance_score == pytest.approx(0.5, abs=1e-6)
