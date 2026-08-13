# -*- coding: utf-8 -*-
"""Coverage wave 86 — core/team_messaging (channels, mentions, delivery, error).

Team messaging routes tested as direct coroutine calls with a real in-memory
SQLite session (full schema) and the WebSocket manager fully mocked:

- send_message: persists a TeamMessage row, builds the MessageResponse with
  sender_name from current_user, broadcasts ``team:{team_id}`` over the WS
  manager, returns the response; context_type/context_id passthrough.
- get_messages: team filter, optional context_type/context_id filters, limit,
  desc ordering, sender_name resolution via the sender relationship, and the
  "Unknown" fallback when a message has no sender.

Zero LLM spend, no network, no real WebSocket server.
"""
import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import TeamMessage, User  # noqa: F401 (register models)
from core.team_messaging import MessageCreate, get_messages, send_message


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_user(db, user_id="user-1", first="Ann", last="Lee"):
    user = User(
        id=user_id,
        email=f"{first.lower()}@example.com",
        hashed_password="x",
        first_name=first,
        last_name=last,
        role="member",
        status="active",
        tenant_id="t1",
        workspace_id="w1",
    )
    db.add(user)
    db.commit()
    return user


def _make_message(db, team_id="team-1", user=None, content="hello",
                  context_type=None, context_id=None, created_at=None):
    msg = TeamMessage(
        team_id=team_id,
        user_id=user.id if user else "user-x",
        content=content,
        context_type=context_type,
        context_id=context_id,
        created_at=created_at,
    )
    if user:
        msg.sender = user
    db.add(msg)
    db.commit()
    return msg


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------

def test_send_message_persists_and_broadcasts(db):
    user = _make_user(db)
    manager = AsyncMock()
    with patch("core.team_messaging.manager", manager):
        resp = asyncio.run(send_message(
            team_id="team-1",
            message_data=MessageCreate(content="hello team", context_type="task", context_id="c1"),
            current_user=user,
            db=db,
        ))

    assert resp.id
    assert resp.team_id == "team-1"
    assert resp.user_id == "user-1"
    assert resp.sender_name == "Ann Lee"
    assert resp.content == "hello team"
    assert resp.context_type == "task"
    assert resp.context_id == "c1"
    assert resp.created_at is not None

    row = db.query(TeamMessage).filter(TeamMessage.id == resp.id).first()
    assert row is not None
    assert row.team_id == "team-1"
    assert row.user_id == "user-1"
    assert row.content == "hello team"

    manager.broadcast.assert_awaited_once()
    channel, payload = manager.broadcast.await_args.args
    assert channel == "team:team-1"
    assert payload["type"] == "message.received"
    assert payload["data"]["content"] == "hello team"


def test_send_message_without_context_fields(db):
    user = _make_user(db)
    manager = AsyncMock()
    with patch("core.team_messaging.manager", manager):
        resp = asyncio.run(send_message(
            team_id="team-2",
            message_data=MessageCreate(content="plain"),
            current_user=user,
            db=db,
        ))
    assert resp.content == "plain"
    assert resp.context_type is None
    assert resp.context_id is None


def test_send_message_broadcast_failure_still_returns_response(db):
    """A WS broadcast failure must not 500 the message send (delivery error path)."""
    user = _make_user(db)
    manager = AsyncMock()
    manager.broadcast.side_effect = RuntimeError("ws down")
    with patch("core.team_messaging.manager", manager):
        resp = asyncio.run(send_message(
            team_id="team-3",
            message_data=MessageCreate(content="still delivered"),
            current_user=user,
            db=db,
        ))
    assert resp.content == "still delivered"
    assert db.query(TeamMessage).count() == 1


# ---------------------------------------------------------------------------
# get_messages
# ---------------------------------------------------------------------------

def test_get_messages_returns_all_with_sender_names(db):
    user = _make_user(db)
    _make_message(db, "team-1", user=user, content="first")
    _make_message(db, "team-1", user=user, content="second", context_type="task", context_id="c2")
    _make_message(db, "other-team", user=user, content="ignored")

    resp = asyncio.run(get_messages(team_id="team-1", db=db, current_user=user))
    assert len(resp) == 2
    assert {r.content for r in resp} == {"first", "second"}
    assert all(r.sender_name == "Ann Lee" for r in resp)
    assert resp[0].created_at is not None


def test_get_messages_context_filters_and_limit(db):
    from datetime import datetime, timedelta, timezone
    user = _make_user(db)
    base = datetime.now(timezone.utc)
    for i in range(3):
        _make_message(db, "team-1", user=user, content=f"t{i}",
                      context_type="workflow", context_id="w1",
                      created_at=base + timedelta(seconds=i))
    _make_message(db, "team-1", user=user, content="other", context_type="task", context_id="w1",
                  created_at=base + timedelta(seconds=10))

    resp = asyncio.run(get_messages(
        team_id="team-1", context_type="workflow", context_id="w1", limit=2,
        db=db, current_user=user,
    ))
    assert [r.content for r in resp] == ["t2", "t1"]  # desc order, limit 2


def test_get_messages_unknown_sender(db):
    """Message whose sender row is missing resolves sender_name to 'Unknown'."""
    msg = _make_message(db, "team-1", user=None, content="orphan")
    assert msg.sender is None
    user = _make_user(db)
    resp = asyncio.run(get_messages(team_id="team-1", db=db, current_user=user))
    assert len(resp) == 1
    assert resp[0].sender_name == "Unknown"
