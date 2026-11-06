"""Failure-first contracts for verified chat-session forks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

import core.chat_fork_write_service as service
import integrations.chat_routes as chat_routes
from core.database import Base, get_db
from core.models import AuditLog, ChatMessage, ChatSession, Tenant, User, Workspace
from core.security_dependencies import get_current_user


@pytest.fixture()
def env(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/chat-fork.db",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    seed = Session()
    seed.add_all([
        Tenant(id="t1", name="Tenant One", subdomain="tenant-one"),
        Workspace(id="ws1", name="Workspace One", tenant_id="t1"),
        User(
            id="owner-1", tenant_id="t1", workspace_id="ws1",
            email="owner@example.com", first_name="Owner", last_name="One",
            role="member", status="active", is_active=True),
        User(
            id="other-1", tenant_id="t1", workspace_id="ws1",
            email="other@example.com", first_name="Other", last_name="One",
            role="member", status="active", is_active=True),
        ChatSession(
            id="s1", user_id="owner-1", title="Source Chat",
            metadata_json={}, message_count=4),
        ChatSession(
            id="s-other", user_id="other-1", title="Other Chat",
            metadata_json={}, message_count=1),
    ])
    base = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
    rows = [
        ("s1-m0", "s1", "user", "first question"),
        ("s1-m1", "s1", "assistant", "first answer"),
        ("s1-m2", "s1", "user", "second question"),
        ("s1-m3", "s1", "assistant", "second answer"),
    ]
    for index, (mid, cid, role, content) in enumerate(rows):
        seed.add(ChatMessage(
            id=mid, conversation_id=cid, tenant_id="t1", role=role,
            content=content, created_at=base.replace(minute=index)))
    seed.add(ChatMessage(
        id="s-other-m0", conversation_id="s-other", tenant_id="t1",
        role="user", content="private other", created_at=base))
    seed.commit()
    seed.close()

    sessions = {
        "s1": {"id": "s1", "session_id": "s1", "user_id": "owner-1",
               "title": "Source Chat", "history": [], "context": {}},
        "s-other": {"id": "s-other", "session_id": "s-other",
                    "user_id": "other-1", "title": "Other Chat",
                    "history": [], "context": {}},
    }

    def get_or_create(user_id, session_id):
        return sessions.setdefault(session_id, {
            "id": session_id, "session_id": session_id, "user_id": user_id,
            "title": None, "history": [], "context": {},
        })

    fake_orchestrator = SimpleNamespace(
        conversation_sessions=sessions,
        _get_or_create_session=get_or_create,
        session_manager=SimpleNamespace(),
    )
    monkeypatch.setattr(chat_routes, "chat_orchestrator", fake_orchestrator)

    app = FastAPI()
    app.include_router(chat_routes.router)

    def db_override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_override

    def client(user: User):
        scoped = FastAPI()
        scoped.include_router(chat_routes.router)
        scoped.dependency_overrides[get_db] = db_override
        scoped.dependency_overrides[get_current_user] = lambda: user
        return TestClient(scoped, raise_server_exceptions=False)

    actors = {
        "owner-1": Session().query(User).filter(User.id == "owner-1").one(),
        "other-1": Session().query(User).filter(User.id == "other-1").one(),
    }
    yield SimpleNamespace(
        engine=engine, Session=Session, app=app, client=client,
        actors=actors, sessions=sessions,
    )


def _sessions(env, user_id=None):
    db = env.Session()
    try:
        query = db.query(ChatSession)
        if user_id is not None:
            query = query.filter(ChatSession.user_id == user_id)
        return query.all()
    finally:
        db.close()


def _messages(env, conversation_id):
    db = env.Session()
    try:
        return db.query(ChatMessage).filter(
            ChatMessage.conversation_id == conversation_id).all()
    finally:
        db.close()


def _audits(env, operation_id=None):
    db = env.Session()
    try:
        query = db.query(AuditLog)
        if operation_id is not None:
            query = query.filter(AuditLog.id == operation_id)
        return query.all()
    finally:
        db.close()


def _fork(client, session_id="s1", operation_id="fork-one", **body):
    return client.post(
        f"/api/chat/sessions/{session_id}/fork"
        f"?operation_id={operation_id}", json=body)


def test_owner_fork_copies_full_conversation_with_audit(env, caplog):
    response = _fork(env.client(env.actors["owner-1"]))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["messages_copied"] == 4
    assert body["forked_from"] == "s1"
    assert body["title"] == "Fork: Source Chat"
    assert body["verification"]["status"] == "verified"
    assert env.sessions[body["session_id"]]["user_id"] == "owner-1"

    fork = _sessions(env, "owner-1")
    assert len(fork) == 2  # source + fork
    fork_row = next(row for row in fork if row.id != "s1")
    assert fork_row.metadata_json["forked_from"] == "s1"
    assert fork_row.message_count == 4
    copied = _messages(env, fork_row.id)
    assert [m.content for m in copied] == [
        "first question", "first answer", "second question", "second answer"]
    assert len(_messages(env, "s1")) == 4  # source untouched

    audit = _audits(env, "chat-fork:fork-one")[0]
    assert audit.action == "chat_session_forked"
    assert audit.user_id == "owner-1"
    metadata = json.loads(audit.metadata_json)
    assert metadata["source_session_id"] == "s1"
    assert metadata["target_id"] == fork_row.id
    for secret in ("first question", "first answer", "Source Chat"):
        assert secret not in (audit.metadata_json or "")
        assert secret not in (audit.description or "")
        assert secret not in caplog.text


def test_prefix_fork_is_inclusive_and_source_unchanged(env):
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="prefix",
        up_to_message_id="s1-m1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["messages_copied"] == 2
    copied = _messages(env, body["session_id"])
    assert [m.content for m in copied] == ["first question", "first answer"]
    assert len(_messages(env, "s1")) == 4


def test_unknown_or_empty_source_keeps_legacy_no_effect(env):
    client = env.client(env.actors["owner-1"])
    unknown = _fork(client, session_id="missing", operation_id="unknown")
    assert unknown.status_code == 200, unknown.text
    assert unknown.json() == {"success": False, "error": "Session not found"}

    empty = _fork(
        client, operation_id="boundary", up_to_message_id="ghost")
    assert empty.status_code == 200, empty.text
    assert empty.json()["success"] is False
    assert "not found in session" in empty.json()["error"]
    assert [row.id for row in _sessions(env, "owner-1")] == ["s1"]
    assert _audits(env) == []


def test_cross_user_fork_is_refused(env):
    response = _fork(
        env.client(env.actors["owner-1"]), session_id="s-other",
        operation_id="cross")
    assert response.status_code == 403, response.text
    assert _sessions(env, "other-1")[0].id == "s-other"
    assert _audits(env) == []


def test_replay_changed_prefix_and_missing_fork(env):
    client = env.client(env.actors["owner-1"])
    first = _fork(client, operation_id="replay")
    assert first.status_code == 200, first.text
    fork_id = first.json()["session_id"]

    replay = _fork(client, operation_id="replay")
    assert replay.status_code == 200, replay.text
    assert replay.json()["verification"]["status"] == "already_applied"
    assert len(_audits(env)) == 1

    changed = _fork(
        client, operation_id="replay", up_to_message_id="s1-m1")
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["error"]["code"] == "OPERATION_CONFLICT"

    db = env.Session()
    try:
        db.query(ChatMessage).filter(
            ChatMessage.conversation_id == fork_id).delete()
        db.query(ChatSession).filter(ChatSession.id == fork_id).delete()
        db.commit()
    finally:
        db.close()
    missing = _fork(client, operation_id="replay")
    assert missing.status_code == 503, missing.text
    assert missing.json()["detail"]["error"]["code"] == (
        "CHAT_FORK_COMMITTED_UNVERIFIED")


def test_stale_source_before_claim_refuses(env, monkeypatch):
    original = service._load_source_messages
    changed = {"done": False}

    def load_then_change(db, session_id):
        rows = original(db, session_id)
        if not changed["done"] and session_id == "s1":
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(ChatSession).where(
                    ChatSession.id == "s1").values(title="Peer Title"))
                peer.commit()
            finally:
                peer.close()
        return rows

    monkeypatch.setattr(service, "_load_source_messages", load_then_change)
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="stale")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_SOURCE"
    assert len(_sessions(env, "owner-1")) == 1
    assert _audits(env) == []


def test_stale_message_content_before_claim_refuses(env, monkeypatch):
    """A message edit after the snapshot read cannot be forked as stale text."""
    original = service._load_source_messages
    changed = {"done": False}

    def load_then_change(db, session_id):
        rows = original(db, session_id)
        if not changed["done"] and session_id == "s1":
            changed["done"] = True
            peer = env.Session()
            try:
                peer.execute(update(ChatMessage).where(
                    ChatMessage.id == "s1-m1").values(
                        content="peer edited answer"))
                peer.commit()
            finally:
                peer.close()
        return rows

    monkeypatch.setattr(service, "_load_source_messages", load_then_change)
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="stale-message")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["error"]["code"] == "STALE_SOURCE"
    assert len(_sessions(env, "owner-1")) == 1
    assert _audits(env) == []


@pytest.mark.parametrize("change", ["deactivate", "tenant_move"])
def test_authority_change_before_claim_refuses(env, monkeypatch, change):
    original = service._load_source_messages
    changed = {"done": False}

    def load_then_change(db, session_id):
        rows = original(db, session_id)
        if not changed["done"] and session_id == "s1":
            changed["done"] = True
            peer = env.Session()
            try:
                values = (
                    {"status": "inactive", "is_active": False}
                    if change == "deactivate"
                    else {"tenant_id": "t2", "workspace_id": "ws2"})
                peer.execute(update(User).where(
                    User.id == "owner-1").values(**values))
                peer.commit()
            finally:
                peer.close()
        return rows

    monkeypatch.setattr(service, "_load_source_messages", load_then_change)
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="authority")
    assert response.status_code in (401, 403, 409), response.text
    assert response.json()["detail"]["verification"]["effect"] == "none"
    assert len(_sessions(env, "owner-1")) == 1
    assert _audits(env) == []


def test_audit_rollback_removes_fork_and_copies(env, monkeypatch):
    original = service._audit_row

    def invalid_audit(**kwargs):
        row = original(**kwargs)
        row.action = None
        return row

    monkeypatch.setattr(service, "_audit_row", invalid_audit)
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="rollback")
    assert response.status_code == 409, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "CHAT_FORK_TRANSACTION_ROLLED_BACK"
    assert detail["verification"]["effect"] == "none"
    assert len(_sessions(env, "owner-1")) == 1
    assert _audits(env) == []


def test_post_commit_readback_is_committed_unverified(env, monkeypatch):
    def unavailable(_db, expected):
        return {
            "status": "unavailable",
            "audit_id": expected["operation_id"],
        }

    monkeypatch.setattr(service, "_verify_audit", unavailable)
    response = _fork(
        env.client(env.actors["owner-1"]), operation_id="readback")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "CHAT_FORK_COMMITTED_UNVERIFIED"
    assert detail["verification"]["effect"] == "committed"
    assert len(_sessions(env, "owner-1")) == 2
    assert len(_audits(env, "chat-fork:readback")) == 1


def test_lost_confirmation_is_effect_unknown_with_identity(env, caplog):
    db = env.Session()
    try:
        def lost_commit():
            raise RuntimeError("lost confirmation SYNTHETIC-CHAT-SECRET")

        db.commit = lost_commit
        result = service.fork_chat_session(
            db, actor=env.actors["owner-1"], session_id="s1",
            operation_id="lost-confirmation")
    finally:
        db.rollback()
        db.close()

    assert result["status"] == "effect_unknown"
    assert result["verification"]["effect"] == "unknown"
    assert result["verification"]["replay"] == "do_not_repeat"
    assert result["operation_id"] == "chat-fork:lost-confirmation"
    assert "SYNTHETIC-CHAT-SECRET" not in json.dumps(result)
    assert "SYNTHETIC-CHAT-SECRET" not in caplog.text
    assert len(_sessions(env, "owner-1")) == 1


@pytest.mark.parametrize("field", [
    "action",
    "user_id",
    "tenant_id",
    "resource",
    "success",
    "security_level",
    "metadata_target_id",
    "metadata_source_session_id",
    "metadata_prior_digest",
    "metadata_result_digest",
    "metadata_request_digest",
])
def test_wrong_audit_receipt_is_never_verified(env, monkeypatch, field):
    original = service._audit_row

    def wrong_audit(**kwargs):
        row = original(**kwargs)
        metadata = json.loads(row.metadata_json or "{}")
        if field == "action":
            row.action = "wrong-action"
        elif field == "user_id":
            row.user_id = "other-1"
        elif field == "tenant_id":
            row.tenant_id = "t2"
        elif field == "resource":
            row.resource = "chat_session:other"
        elif field == "success":
            row.success = False
        elif field == "security_level":
            row.security_level = "low"
        elif field == "metadata_target_id":
            metadata["target_id"] = "other"
        elif field == "metadata_source_session_id":
            metadata["source_session_id"] = "other"
        elif field == "metadata_prior_digest":
            metadata["prior_digest"] = "wrong-prior"
        elif field == "metadata_result_digest":
            metadata["result_digest"] = "wrong-result"
        elif field == "metadata_request_digest":
            metadata["request_digest"] = "wrong-request"
        row.metadata_json = json.dumps(metadata)
        return row

    monkeypatch.setattr(service, "_audit_row", wrong_audit)
    response = _fork(
        env.client(env.actors["owner-1"]),
        operation_id=f"audit-{field}")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"]["code"] == "CHAT_FORK_COMMITTED_UNVERIFIED"
    assert detail["verification"]["status"] in ("refuted", "unavailable")
    assert detail["verification"]["effect"] == "committed"


def test_anonymous_requests_are_refused(env):
    env.app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(env.app, raise_server_exceptions=False)
    assert client.post(
        "/api/chat/sessions/s1/fork", json={}).status_code == 401
    assert len(_sessions(env, "owner-1")) == 1
    assert _audits(env) == []
