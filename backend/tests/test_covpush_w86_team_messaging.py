# -*- coding: utf-8 -*-
"""Synthetic authorization coverage for core/team_messaging.

Every scenario uses an in-memory SQLite database with the application schema.
No live service, network, WebSocket server, or external fixture is involved.

Positive cases prove that a caller who is a team member in the current
workspace and tenant can read history and persist messages.  Refusal cases
prove that missing membership, a different workspace, a different tenant, or a
missing team all produce the same fixed 404 before any read or write.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import Team, TeamMessage, User, Workspace
from core.team_messaging import (
    MAX_HISTORY_LIMIT,
    MAX_MESSAGE_LENGTH,
    TEAM_NOT_FOUND_DETAIL,
    MessageCreate,
    get_messages,
    get_my_teams,
    send_message,
)


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _make_workspace(db, workspace_id="w1", tenant_id="t1"):
    workspace = Workspace(
        id=workspace_id,
        name=f"Workspace {workspace_id}",
        tenant_id=tenant_id,
    )
    db.add(workspace)
    db.commit()
    return workspace


def _make_team(db, team_id="team-1", workspace_id="w1", name=None):
    team = Team(
        id=team_id,
        name=name or f"Team {team_id}",
        workspace_id=workspace_id,
    )
    db.add(team)
    db.commit()
    return team


def _make_user(db, user_id="user-1", first="Ann", last="Lee",
               tenant_id="t1", workspace_id="w1", teams=None):
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        hashed_password="x",
        first_name=first,
        last_name=last,
        role="member",
        status="active",
        tenant_id=tenant_id,
        workspace_id=workspace_id,
    )
    if teams:
        user.teams.extend(teams)
    db.add(user)
    db.commit()
    return user


def _member_setup(db, team_id="team-1", user_id="user-1",
                  workspace_id="w1", tenant_id="t1", team_name=None):
    _make_workspace(db, workspace_id, tenant_id)
    team = _make_team(db, team_id, workspace_id, team_name)
    user = _make_user(
        db,
        user_id=user_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        teams=[team],
    )
    return user, team


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


def _assert_fixed_404(exc_info):
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == TEAM_NOT_FOUND_DETAIL


# ---------------------------------------------------------------------------
# Positive authorization
# ---------------------------------------------------------------------------

def test_send_message_authorized_persists_without_shared_broadcast(db):
    user, _ = _member_setup(db)
    with patch("core.websockets.manager.broadcast", new_callable=AsyncMock) as broadcast:
        resp = asyncio.run(send_message(
            team_id="team-1",
            message_data=MessageCreate(
                content="hello team",
                context_type="task",
                context_id="c1",
            ),
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

    # Confidential text is intentionally not published to the shared channel.
    broadcast.assert_not_awaited()


def test_send_message_authorized_without_context_fields(db):
    user, _ = _member_setup(db)
    resp = asyncio.run(send_message(
        team_id="team-1",
        message_data=MessageCreate(content="plain"),
        current_user=user,
        db=db,
    ))
    assert resp.content == "plain"
    assert resp.context_type is None
    assert resp.context_id is None


def test_get_messages_authorized_returns_all_with_sender_names(db):
    user, _ = _member_setup(db)
    _make_team(db, "other-team", "w1")
    _make_message(db, "team-1", user=user, content="first")
    _make_message(db, "team-1", user=user, content="second",
                  context_type="task", context_id="c2")
    _make_message(db, "other-team", user=user, content="ignored")

    resp = asyncio.run(get_messages(team_id="team-1", db=db, current_user=user))
    assert len(resp) == 2
    assert {r.content for r in resp} == {"first", "second"}
    assert all(r.sender_name == "Ann Lee" for r in resp)
    assert resp[0].created_at is not None


def test_get_messages_authorized_context_filters_and_limit(db):
    user, _ = _member_setup(db)
    base = datetime.now(timezone.utc)
    for i in range(3):
        _make_message(db, "team-1", user=user, content=f"t{i}",
                      context_type="workflow", context_id="w1",
                      created_at=base + timedelta(seconds=i))
    _make_message(db, "team-1", user=user, content="other",
                  context_type="task", context_id="w1",
                  created_at=base + timedelta(seconds=10))

    resp = asyncio.run(get_messages(
        team_id="team-1", context_type="workflow", context_id="w1", limit=2,
        db=db, current_user=user,
    ))
    assert [r.content for r in resp] == ["t2", "t1"]  # desc order, limit 2


def test_get_messages_authorized_unknown_sender(db):
    """Message whose sender row is missing resolves sender_name to 'Unknown'."""
    user, _ = _member_setup(db)
    msg = _make_message(db, "team-1", user=None, content="orphan")
    assert msg.sender is None
    resp = asyncio.run(get_messages(team_id="team-1", db=db, current_user=user))
    assert len(resp) == 1
    assert resp[0].sender_name == "Unknown"


# ---------------------------------------------------------------------------
# Message validation: reject bad writes, leave older stored rows readable
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("content", ["", " ", "\t", "\n", "  \t\n  "])
def test_message_create_rejects_blank_content(content):
    with pytest.raises(ValidationError):
        MessageCreate(content=content)


def test_message_create_rejects_content_over_max_length():
    with pytest.raises(ValidationError):
        MessageCreate(content="x" * (MAX_MESSAGE_LENGTH + 1))


def test_message_create_accepts_boundary_length_and_preserves_text():
    content = "x" * MAX_MESSAGE_LENGTH
    message = MessageCreate(content=content)
    assert message.content == content


def test_send_message_preserves_nonblank_text_exactly(db):
    user, _ = _member_setup(db)
    content = "  hello team\n"
    resp = asyncio.run(send_message(
        team_id="team-1",
        message_data=MessageCreate(content=content),
        current_user=user,
        db=db,
    ))

    assert resp.content == content
    row = db.query(TeamMessage).filter(TeamMessage.id == resp.id).first()
    assert row is not None
    assert row.content == content


def test_history_keeps_older_unvalidated_records_readable(db):
    """Rows written before validation are returned verbatim, not rejected."""
    user, _ = _member_setup(db)
    blank_content = "   \t\n "
    long_content = "x" * (MAX_MESSAGE_LENGTH + 100)
    _make_message(db, "team-1", user=user, content=blank_content)
    _make_message(db, "team-1", user=user, content=long_content)

    resp = asyncio.run(get_messages(team_id="team-1", db=db, current_user=user))

    assert {r.content for r in resp} == {blank_content, long_content}


# ---------------------------------------------------------------------------
# Refusals: same fixed 404 before read or persist
# ---------------------------------------------------------------------------

def test_send_message_refuses_non_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t1")
    _make_team(db, "team-1", "w1")
    user = _make_user(db, tenant_id="t1", workspace_id="w1")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(send_message(
            team_id="team-1",
            message_data=MessageCreate(content="confidential"),
            current_user=user,
            db=db,
        ))

    _assert_fixed_404(exc_info)
    assert db.query(TeamMessage).count() == 0


def test_send_message_refuses_cross_workspace_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t1")
    _make_workspace(db, "w2", "t1")
    team = _make_team(db, "team-1", "w1")
    user = _make_user(
        db, tenant_id="t1", workspace_id="w2", teams=[team],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(send_message(
            team_id="team-1",
            message_data=MessageCreate(content="confidential"),
            current_user=user,
            db=db,
        ))

    _assert_fixed_404(exc_info)
    assert db.query(TeamMessage).count() == 0


def test_send_message_refuses_cross_tenant_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t2")
    team = _make_team(db, "team-1", "w1")
    user = _make_user(
        db, tenant_id="t1", workspace_id="w1", teams=[team],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(send_message(
            team_id="team-1",
            message_data=MessageCreate(content="confidential"),
            current_user=user,
            db=db,
        ))

    _assert_fixed_404(exc_info)
    assert db.query(TeamMessage).count() == 0


def test_get_messages_refuses_non_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t1")
    _make_team(db, "team-1", "w1")
    _make_message(db, "team-1", user=None, content="confidential")
    user = _make_user(db, tenant_id="t1", workspace_id="w1")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_messages(
            team_id="team-1", db=db, current_user=user,
        ))

    _assert_fixed_404(exc_info)


def test_get_messages_refuses_cross_workspace_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t1")
    _make_workspace(db, "w2", "t1")
    team = _make_team(db, "team-1", "w1")
    _make_message(db, "team-1", user=None, content="confidential")
    user = _make_user(
        db, tenant_id="t1", workspace_id="w2", teams=[team],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_messages(
            team_id="team-1", db=db, current_user=user,
        ))

    _assert_fixed_404(exc_info)


def test_get_messages_refuses_cross_tenant_member_with_fixed_404(db):
    _make_workspace(db, "w1", "t2")
    team = _make_team(db, "team-1", "w1")
    _make_message(db, "team-1", user=None, content="confidential")
    user = _make_user(
        db, tenant_id="t1", workspace_id="w1", teams=[team],
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_messages(
            team_id="team-1", db=db, current_user=user,
        ))

    _assert_fixed_404(exc_info)


def test_missing_team_uses_same_fixed_404(db):
    user, _ = _member_setup(db)

    with pytest.raises(HTTPException) as send_exc:
        asyncio.run(send_message(
            team_id="does-not-exist",
            message_data=MessageCreate(content="confidential"),
            current_user=user,
            db=db,
        ))
    with pytest.raises(HTTPException) as get_exc:
        asyncio.run(get_messages(
            team_id="does-not-exist", db=db, current_user=user,
        ))

    _assert_fixed_404(send_exc)
    _assert_fixed_404(get_exc)
    assert db.query(TeamMessage).count() == 0


# ---------------------------------------------------------------------------
# GET /api/teams/mine and bounded history
# ---------------------------------------------------------------------------

def test_mine_returns_only_scoped_member_teams_with_ids_and_names(db):
    _make_workspace(db, "w1", "t1")
    _make_workspace(db, "w2", "t1")
    _make_workspace(db, "w3", "t2")

    alpha = _make_team(db, "team-a", "w1", "Alpha")
    beta = _make_team(db, "team-b", "w1", "Beta")
    _make_team(db, "team-no-member", "w1", "No Member")
    other_workspace = _make_team(db, "team-other-ws", "w2", "Other Workspace")
    other_tenant = _make_team(db, "team-other-tenant", "w3", "Other Tenant")

    user = _make_user(
        db,
        tenant_id="t1",
        workspace_id="w1",
        teams=[alpha, beta, other_workspace, other_tenant],
    )

    resp = asyncio.run(get_my_teams(db=db, current_user=user))

    assert [(team.id, team.name) for team in resp] == [
        ("team-a", "Alpha"),
        ("team-b", "Beta"),
    ]
    assert set(resp[0].dict().keys()) == {"id", "name"}


def test_mine_returns_no_teams_without_membership(db):
    _make_workspace(db, "w1", "t1")
    _make_team(db, "team-1", "w1", "Hidden")
    user = _make_user(db, tenant_id="t1", workspace_id="w1")

    resp = asyncio.run(get_my_teams(db=db, current_user=user))
    assert resp == []


def test_history_limit_is_capped(db):
    user, _ = _member_setup(db)
    base = datetime.now(timezone.utc)
    for i in range(MAX_HISTORY_LIMIT + 5):
        _make_message(
            db, "team-1", user=user, content=f"m{i}",
            created_at=base + timedelta(seconds=i),
        )

    resp = asyncio.run(get_messages(
        team_id="team-1", limit=MAX_HISTORY_LIMIT * 100,
        db=db, current_user=user,
    ))

    assert len(resp) == MAX_HISTORY_LIMIT
    assert resp[0].content == f"m{MAX_HISTORY_LIMIT + 4}"  # newest first


def test_history_limit_floor_prevents_negative_unbounded_query(db):
    user, _ = _member_setup(db)
    base = datetime.now(timezone.utc)
    for i in range(2):
        _make_message(
            db, "team-1", user=user, content=f"m{i}",
            created_at=base + timedelta(seconds=i),
        )

    resp = asyncio.run(get_messages(
        team_id="team-1", limit=-10, db=db, current_user=user,
    ))

    assert len(resp) == 1
