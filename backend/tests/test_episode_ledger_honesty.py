"""Episode ledger honesty — the graduation evidence must not be stamped.

Regression context (Sep 1, 2026): a canvas hire showed "Readiness for
INTERN: 72/100 · ready" that the supervisor called fake. Verified: the
AgentEpisode model's ``default=1.0`` stamped a PERFECT constitutional score
on every episode that never measured compliance (SQLAlchemy applies the
Python-side default even when the writer passes None explicitly), and the
chat-segmentation writer hardcoded ``confidence_score=0.5`` — so the
readiness constitutional factor (0.25 weight) was free credit and the
confidence factor (0.2) read a constant instead of the hire's real 0.3.
With honest inputs the same agent scores 57.2/100 — NOT ready.
"""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import (
    AgentEpisode,
    AgentRegistry,
    Base,
    ChatMessage,
    ChatSession,
)


@pytest.fixture()
def db():
    fd, path = None, None
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    Sess = sessionmaker(bind=eng, expire_on_commit=False)
    session = Sess()
    try:
        yield session
    finally:
        session.close()
        eng.dispose()
        os.unlink(path)


def _agent(db, confidence=0.3):
    agent = AgentRegistry(
        id=f"ag-{uuid.uuid4().hex[:8]}",
        name="Hire",
        category="sales",
        module_path="m",
        class_name="C",
        status="student",
        confidence_score=confidence,
        capabilities=["send_email"],
        configuration={},
        workspace_id="default",
        tenant_id="default",
    )
    db.add(agent)
    db.commit()
    return agent


def _chat_session(db, agent, user_id="user-1"):
    """A minimal chat-only session (1 user + 1 assistant message) — the
    shape every co-editor conversation takes."""
    cs = ChatSession(id=f"cs-{uuid.uuid4().hex[:8]}", user_id=user_id, title="t")
    db.add(cs)
    now = datetime.now(timezone.utc)
    db.add(ChatMessage(
        conversation_id=cs.id, tenant_id="default", role="user",
        content="check the lead's website and verify if they are a dealer",
        created_at=now,
    ))
    db.add(ChatMessage(
        conversation_id=cs.id, tenant_id="default", role="assistant",
        content="Here is what I found about the lead.",
        created_at=now,
        agent_id=agent.id,
    ))
    db.commit()
    return cs


@pytest.mark.asyncio
async def test_chat_episode_records_no_unmeasured_constitutional_credit(db):
    """A chat-segmented episode must NOT carry a constitutional score nothing
    measured — it persists as NULL so the readiness scorer renormalizes the
    factor away instead of awarding free 1.0 credit."""
    from core.episode_segmentation_service import EpisodeSegmentationService
    from unittest.mock import AsyncMock, patch

    agent = _agent(db)
    cs = _chat_session(db, agent)
    svc = EpisodeSegmentationService(db=db, lancedb=None)

    with patch.object(EpisodeSegmentationService, "_create_segments", AsyncMock()), \
         patch.object(EpisodeSegmentationService, "_archive_to_lancedb", AsyncMock()):
        out = await svc.create_episode_from_session(cs.id, agent.id)

    assert out is not None
    row = db.query(AgentEpisode).filter(AgentEpisode.id == out["id"]).first()
    assert row is not None
    assert row.constitutional_score is None          # no unmeasured credit
    assert row.confidence_score == pytest.approx(0.3)  # the hire's REAL confidence


@pytest.mark.asyncio
async def test_chat_episode_confidence_tracks_the_agent(db):
    """Two hires with different real confidences must produce episodes with
    DIFFERENT recorded confidences — the factor is per-agent state, not a
    global constant."""
    from core.episode_segmentation_service import EpisodeSegmentationService
    from unittest.mock import AsyncMock, patch

    confident = _agent(db, confidence=0.44)
    struggling = _agent(db, confidence=0.05)
    cs1 = _chat_session(db, confident)
    cs2 = _chat_session(db, struggling)
    svc = EpisodeSegmentationService(db=db, lancedb=None)

    for cs, agent in ((cs1, confident), (cs2, struggling)):
        with patch.object(EpisodeSegmentationService, "_create_segments", AsyncMock()), \
             patch.object(EpisodeSegmentationService, "_archive_to_lancedb", AsyncMock()):
            await svc.create_episode_from_session(cs.id, agent.id)

    rows = db.query(AgentEpisode).all()
    confs = {r.agent_id: r.confidence_score for r in rows}
    assert confs[confident.id] == pytest.approx(0.44)
    assert confs[struggling.id] == pytest.approx(0.05)
