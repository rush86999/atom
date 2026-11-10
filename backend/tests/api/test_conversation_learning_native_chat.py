"""Real scratch SQL + JWT tests for native-chat conversation learning."""
from __future__ import annotations

import datetime
import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.conversation_learning_routes import router
from core.auth import create_access_token
from core.database import Base, get_db
from core.models import (
    AgentRegistry, Canvas, CanvasAudit, ChatMessage, ChatSession,
    ConversationEvent, Tenant, User, Workspace,
)


class World:
    def __init__(self, tmp_path):
        self.engine = create_engine(
            f"sqlite:///{tmp_path}/learn.db",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        s = uuid.uuid4().hex[:8]
        self.tenant = f"tenant-{s}"
        self.ws = f"ws-{s}"
        self.user = f"user-{s}"
        self.foreign_tenant = f"tenant-f-{s}"
        self.foreign_ws = f"ws-f-{s}"
        self.foreign_user = f"user-f-{s}"
        self.peer = f"user-p-{s}"
        self.inactive = f"user-i-{s}"
        self.chat = f"chat-{s}"
        self.foreign_chat = f"chat-f-{s}"
        self.email = f"email-{s}"
        self.collision_email = self.chat
        self.collision_email_msg = f"ce-{s}"
        self.user_msg = f"m-user-{s}"
        self.assistant_msg = f"m-assistant-{s}"
        self.system_msg = f"m-system-{s}"
        self.agent = f"agent-{s}"
        now = datetime.datetime.now(datetime.timezone.utc)
        t_user = now
        t_assistant = now + datetime.timedelta(seconds=1)
        t_system = now + datetime.timedelta(seconds=2)
        with self.Session() as db:
            db.add(Tenant(id=self.tenant, name="T", subdomain=f"t-{s}",
                          edition="personal", is_active=True))
            db.add(Workspace(id=self.ws, name="W", tenant_id=self.tenant))
            db.add(Tenant(id=self.foreign_tenant, name="F", subdomain=f"f-{s}",
                          edition="personal", is_active=True))
            db.add(Workspace(id=self.foreign_ws, name="FW", tenant_id=self.foreign_tenant))
            db.add_all([
                User(id=self.user, tenant_id=self.tenant, email=f"u-{s}@example.com",
                     first_name="U", last_name="Ser", role="member", status="active",
                     workspace_id=self.ws, is_active=True),
                User(id=self.foreign_user, tenant_id=self.foreign_tenant,
                     email=f"f-{s}@example.com", first_name="F", last_name="User",
                     role="member", status="active", workspace_id=self.foreign_ws,
                     is_active=True),
                User(id=self.peer, tenant_id=self.tenant,
                     email=f"p-{s}@example.com", first_name="P", last_name="Peer",
                     role="member", status="active", workspace_id=self.ws,
                     is_active=True),
                User(id=self.inactive, tenant_id=self.tenant,
                     email=f"i-{s}@example.com", first_name="I", last_name="User",
                     role="member", status="inactive", workspace_id=self.ws,
                     is_active=False),
            ])
            db.add(AgentRegistry(
                id=self.agent, name="Pricing Agent", category="finance",
                role="agent", type="personal", capabilities=[], module_path="core.generic_agent",
                class_name="GenericAgent", user_id=self.user, workspace_id=self.ws,
                tenant_id=self.tenant, status="autonomous", enabled=True,
            ))
            db.flush()
            db.add_all([
                ChatSession(id=self.chat, user_id=self.user, title="Pricing chat",
                            message_count=3, created_at=now, updated_at=now),
                ChatSession(id=self.foreign_chat, user_id=self.foreign_user,
                            title="Foreign chat", message_count=1,
                            created_at=now, updated_at=now),
            ])
            db.add_all([
                ChatMessage(id=self.user_msg, conversation_id=self.chat,
                            tenant_id=self.tenant, role="user",
                            content="Always apply the 10% annual-prepay exception.",
                            created_at=t_user),
                ChatMessage(id=self.assistant_msg, conversation_id=self.chat,
                            tenant_id=self.tenant, role="assistant",
                            content="Understood, I will apply it.",
                            created_at=t_assistant),
                ChatMessage(id=self.system_msg, conversation_id=self.chat,
                            tenant_id=self.tenant, role="system",
                            content="tool_result: discount=10",
                            created_at=t_system),
                ChatMessage(id=f"m-f-{s}", conversation_id=self.foreign_chat,
                            tenant_id=self.foreign_tenant, role="user",
                            content="Foreign secret", created_at=now),
            ])
            canvas = Canvas(id=f"c-{s}", tenant_id=self.tenant, workspace_id=self.ws,
                            created_by=self.user, name="Email", canvas_type="email",
                            status="active")
            fcanvas = Canvas(id=f"cf-{s}", tenant_id=self.foreign_tenant,
                             workspace_id=self.foreign_ws, created_by=self.foreign_user,
                             name="FEmail", canvas_type="email", status="active")
            db.add_all([canvas, fcanvas])
            db.flush()
            def add_audit(cid, tid, thread, subject, body, mid, uid):
                db.add(CanvasAudit(
                    id=str(uuid.uuid4()), canvas_id=cid, tenant_id=tid,
                    action_type="form_submit", user_id=uid, canvas_type="email",
                    details_json={"thread_id": thread, "subject": subject,
                                  "messages": [{"message_id": mid,
                                                "provider": "email_canvas",
                                                "body": body, "from_email": "x@example.com",
                                                "to_emails": [f"u-{s}@example.com"],
                                                "timestamp": now.isoformat()}]},
                    created_at=now,
                ))
            add_audit(canvas.id, self.tenant, self.email, "Email positive",
                      "Use net price on annual prepay.", f"e-{s}", self.user)
            add_audit(canvas.id, self.tenant, self.collision_email, "Collision email",
                      "Email body with the same literal id.",
                      self.collision_email_msg, self.user)
            add_audit(fcanvas.id, self.foreign_tenant, f"femail-{s}", "Foreign email",
                      "Foreign body", f"fe-{s}", self.foreign_user)
            db.commit()

    def token(self, uid):
        with self.Session() as db:
            user = db.query(User).filter(User.id == uid).one()
            return create_access_token({"sub": user.id}, user=user)

    def client(self, engine=None):
        engine = engine or self.engine
        Session = sessionmaker(bind=engine, expire_on_commit=False)
        app = FastAPI()
        app.include_router(router)
        def override():
            session = Session()
            try:
                yield session
            finally:
                session.close()
        app.dependency_overrides[get_db] = override
        return TestClient(app, base_url="http://testserver")

    def call(self, client, method, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        fn = getattr(client, method)
        return fn(path, headers=headers, **kwargs)


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path)


def test_native_positive_email_positive_and_typed_evidence(world):
    c = world.client()
    tok = world.token(world.user)
    r = world.call(c, "get", "/api/conversation-learning/threads", tok)
    assert r.status_code == 200
    threads = r.json()["threads"]
    kinds = {(t["source_kind"], t["thread_id"]): t for t in threads}
    assert ("native_chat", world.chat) in kinds
    assert ("email", world.email) in kinds
    assert ("native_chat", world.foreign_chat) not in kinds
    native = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                        json={"thread_id": world.chat, "source_kind": "native_chat"})
    assert native.status_code == 200
    body = native.json()
    assert body["source_kind"] == "native_chat"
    assert body["source_scope"] == "user_global"
    assert body["coverage"]["source_access"] == "available"
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant", "system"]
    assert body["messages"][0]["authored_segments"]
    assert not body["messages"][1]["authored_segments"]
    assert not body["messages"][1]["quoted_segments"]
    assert body["messages"][1]["role"] == "assistant"
    assert body["messages"][2]["role"] == "system"
    email = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                       json={"thread_id": world.email})
    assert email.status_code == 200
    assert email.json()["source_kind"] == "email"


def test_typed_collision_twins_and_unknown_kind(world):
    c = world.client()
    tok = world.token(world.user)
    email = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                       json={"thread_id": world.collision_email, "source_kind": "email"})
    assert email.status_code == 200 and email.json()["source_kind"] == "email"
    native = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                        json={"thread_id": world.chat, "source_kind": "native_chat"})
    assert native.status_code == 200 and native.json()["source_kind"] == "native_chat"
    bare = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                      json={"thread_id": f"nativechat:{world.chat}"})
    assert bare.status_code == 200
    assert bare.json()["source_kind"] == "email"
    assert bare.json()["coverage"]["source_access"] == "missing"
    unknown = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                         json={"thread_id": world.chat, "source_kind": "bogus"})
    assert unknown.status_code == 400

    native_c = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                          json=_candidate_payload(world, world.user_msg))
    assert native_c.status_code == 200, native_c.text
    email_c = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                         json={
                             "thread_id": world.collision_email,
                             "source_kind": "email",
                             "agent_id": world.agent,
                             "proposed_lesson": "Email collision lesson.",
                             "applies_to": ["email"],
                             "context": {},
                             "method_status": "not_applicable",
                             "authority_message_id": world.collision_email_msg,
                         })
    assert email_c.status_code == 200, email_c.text
    native_id = native_c.json()["candidate"]["candidate_id"]
    email_id = email_c.json()["candidate"]["candidate_id"]
    native_list = world.call(c, "get",
                             f"/api/conversation-learning/threads/{world.chat}/candidates",
                             tok, params={"source_kind": "native_chat"})
    email_list = world.call(c, "get",
                            f"/api/conversation-learning/threads/{world.collision_email}/candidates",
                            tok, params={"source_kind": "email"})
    assert [x["candidate"]["candidate_id"] for x in native_list.json()["candidates"]] == [native_id]
    assert [x["candidate"]["candidate_id"] for x in email_list.json()["candidates"]] == [email_id]
    wrong = world.call(c, "get",
                       f"/api/conversation-learning/candidates/{native_id}",
                       tok, params={"thread_id": world.chat, "source_kind": "email"})
    assert wrong.status_code == 404


def test_foreign_inactive_and_deleted_native(world):
    c = world.client()
    foreign_tok = world.token(world.foreign_user)
    r = world.call(c, "get", "/api/conversation-learning/threads", foreign_tok)
    ids = {(t["source_kind"], t["thread_id"]) for t in r.json()["threads"]}
    assert ("native_chat", world.foreign_chat) in ids
    assert ("native_chat", world.chat) not in ids
    assert ("email", world.email) not in ids
    inactive = world.call(c, "get", "/api/conversation-learning/threads",
                          world.token(world.inactive))
    assert inactive.status_code == 401
    with world.Session() as db:
        db.query(ChatMessage).filter(ChatMessage.conversation_id == world.chat).delete()
        db.query(ChatSession).filter(ChatSession.id == world.chat).delete()
        db.commit()
    deleted = world.call(c, "post", "/api/conversation-learning/evidence",
                         world.token(world.user),
                         json={"thread_id": world.chat, "source_kind": "native_chat"})
    assert deleted.status_code == 200
    assert deleted.json()["coverage"]["source_access"] == "missing"


def _candidate_payload(world, authority):
    return {
        "thread_id": world.chat,
        "source_kind": "native_chat",
        "agent_id": world.agent,
        "proposed_lesson": "Apply the annual-prepay exception before quoting.",
        "applies_to": ["pricing"],
        "context": {},
        "method_status": "not_applicable",
        "authority_message_id": authority,
        "authority_excerpt": "annual-prepay exception" if authority == world.user_msg else "",
    }


def test_assistant_not_authority_and_native_stale_confirm_promote(world):
    c = world.client()
    tok = world.token(world.user)
    assistant = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                           json=_candidate_payload(world, world.assistant_msg))
    assert assistant.status_code == 400
    assert "authority_not_user_authored" in assistant.text
    created = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                         json=_candidate_payload(world, world.user_msg))
    assert created.status_code == 200, created.text
    candidate = created.json()["candidate"]
    assert candidate["source_kind"] == "native_chat"
    assert candidate["source_revision"]
    listed = world.call(c, "get",
                        f"/api/conversation-learning/threads/{world.chat}/candidates",
                        tok, params={"source_kind": "native_chat"})
    assert listed.status_code == 200
    assert any(x["candidate"]["candidate_id"] == candidate["candidate_id"]
               for x in listed.json()["candidates"])
    wrong_kind = world.call(c, "get",
                            f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
                            tok, params={"thread_id": world.chat, "source_kind": "email"})
    assert wrong_kind.status_code == 404
    wrong_promote = world.call(c, "post",
                               f"/api/conversation-learning/candidates/{candidate['candidate_id']}/promote",
                               tok, json={"thread_id": world.chat, "source_kind": "email",
                                          "reviewer": "owner", "expected_revision": candidate["revision"],
                                          "expected_digest": candidate["digest"]})
    assert wrong_promote.status_code == 404
    confirm = world.call(c, "post",
                         f"/api/conversation-learning/candidates/{candidate['candidate_id']}/confirm",
                         tok, json={"thread_id": world.chat, "source_kind": "native_chat",
                                    "reviewer": "owner", "expected_revision": candidate["revision"]})
    assert confirm.status_code == 200, confirm.text
    confirmed = confirm.json()["candidate"]
    promote = world.call(c, "post",
                         f"/api/conversation-learning/candidates/{candidate['candidate_id']}/promote",
                         tok, json={"thread_id": world.chat, "source_kind": "native_chat",
                                    "reviewer": "owner", "expected_revision": confirmed["revision"],
                                    "expected_digest": confirmed["digest"]})
    assert promote.status_code == 200, promote.text
    assert promote.json()["lesson_id"]
    from core.student_learning_service import get_agent_lessons
    with world.Session() as db:
        lessons = get_agent_lessons(
            db, world.agent, query="annual-prepay exception",
            include_workspace=False, workspace_id=world.ws)
    lesson = next((x for x in lessons
                   if "annual-prepay exception" in str(x.get("lesson") or x.get("summary") or "")), None)
    assert lesson is not None
    provenance = lesson["details"]["conversation_learning"]
    assert provenance["source_kind"] == "native_chat"
    assert provenance["source_revision"] == candidate["source_revision"]
    assert provenance["source_owner_id"] == world.user
    assert provenance["thread_id"] == world.chat
    with world.Session() as db:
        row = db.query(ChatMessage).filter(ChatMessage.id == world.user_msg).one()
        row.content = "Changed content after review."
        db.commit()
    stale_get = world.call(c, "get",
                           f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
                           tok, params={"thread_id": world.chat, "source_kind": "native_chat"})
    assert stale_get.status_code == 200
    assert stale_get.json()["candidate"]["status"] == "invalidated"
    with world.Session() as db:
        lessons_after = get_agent_lessons(
            db, world.agent, query="annual-prepay exception",
            include_workspace=False, workspace_id=world.ws)
    assert not any("annual-prepay exception" in str(x.get("lesson") or x.get("summary") or "")
                   for x in lessons_after)
    with world.Session() as db:
        db.query(ChatMessage).filter(ChatMessage.conversation_id == world.chat).delete()
        db.query(ChatSession).filter(ChatSession.id == world.chat).delete()
        db.commit()
    promote_deleted = world.call(c, "post",
                                 f"/api/conversation-learning/candidates/{candidate['candidate_id']}/promote",
                                 tok, json={"thread_id": world.chat, "source_kind": "native_chat",
                                            "reviewer": "owner", "expected_revision": confirmed["revision"],
                                            "expected_digest": confirmed["digest"]})
    assert promote_deleted.status_code == 409


def _event_count(world) -> int:
    with world.Session() as db:
        return db.query(ConversationEvent).filter_by(
            conversation_id=world.chat).count()


def _owner_candidate(world):
    with world.client() as c:
        created = world.call(c, "post",
                             "/api/conversation-learning/candidates",
                             world.token(world.user),
                             json=_candidate_payload(world, world.user_msg))
    assert created.status_code == 200, created.text
    return created.json()["candidate"]


def test_same_workspace_peer_cannot_read_or_reject_private_candidate(world):
    candidate = _owner_candidate(world)
    before = _event_count(world)
    with world.client() as c:
        read = world.call(
            c, "get",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
            world.token(world.peer),
            params={"thread_id": world.chat,
                    "source_kind": "native_chat"})
        reject = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/reject",
            world.token(world.peer),
            json={"thread_id": world.chat,
                  "source_kind": "native_chat",
                  "reviewer": "peer",
                  "reason": "synthetic unauthorized attempt"})
    assert read.status_code == 404, read.text
    assert reject.status_code == 404, reject.text
    assert _event_count(world) == before


def test_same_workspace_peer_cannot_list_or_mutate_private_candidate(world):
    payload = _candidate_payload(world, world.user_msg)
    payload["method_status"] = "unresolved"
    with world.client() as c:
        created = world.call(c, "post",
                             "/api/conversation-learning/candidates",
                             world.token(world.user), json=payload)
    assert created.status_code == 200, created.text
    candidate = created.json()["candidate"]
    dependency_id = candidate["dependencies"][0]["dependency_id"]
    before = _event_count(world)
    peer = world.token(world.peer)
    body = {"thread_id": world.chat, "source_kind": "native_chat"}
    with world.client() as c:
        listed = world.call(
            c, "get",
            f"/api/conversation-learning/threads/{world.chat}/candidates",
            peer, params={"source_kind": "native_chat"})
        revise = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/revise",
            peer, json={**body, "proposed_lesson": "Peer rewrite"})
        resolve = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/resolve",
            peer, json={**body, "dependency_id": dependency_id,
                        "value": "peer", "confirmed_by": "peer"})
        confirm = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/confirm",
            peer, json={**body, "reviewer": "peer",
                        "expected_revision": candidate["revision"]})
        promote = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/promote",
            peer, json={**body, "reviewer": "peer",
                        "expected_revision": candidate["revision"],
                        "expected_digest": candidate["digest"]})
        apply = world.call(
            c, "post",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}/apply",
            peer, json={**body, "rows": []})
    assert listed.status_code == 200
    assert listed.json()["candidates"] == []
    for response in (revise, resolve, confirm, promote, apply):
        assert response.status_code == 404, response.text
    assert _event_count(world) == before
    owner = world.token(world.user)
    with world.client() as c:
        own = world.call(
            c, "get",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
            owner, params={"thread_id": world.chat,
                           "source_kind": "native_chat"})
    assert own.status_code == 200, own.text


def test_missing_native_owner_fails_closed_for_owner_too(world):
    candidate = _owner_candidate(world)
    with world.Session() as db:
        row = db.query(ConversationEvent).filter(
            ConversationEvent.conversation_id == world.chat).order_by(
                ConversationEvent.created_at.desc()).first()
        payload = json.loads(row.payload_json)
        payload["candidate"]["source_owner_id"] = ""
        row.payload_json = json.dumps(payload)
        db.commit()
    with world.client() as c:
        read = world.call(
            c, "get",
            f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
            world.token(world.user),
            params={"thread_id": world.chat,
                    "source_kind": "native_chat"})
    assert read.status_code == 404, read.text


def test_native_boundaries_truthful_total_and_last_at(world):
    c = world.client()
    tok = world.token(world.user)
    base = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)
    sessions = {}
    with world.Session() as db:
        for n in (199, 200, 201):
            sid = f"boundary-{n}-{world.chat}"
            sessions[n] = sid
            db.add(ChatSession(id=sid, user_id=world.user, title=f"Boundary {n}",
                               message_count=n, created_at=base, updated_at=base))
            db.flush()
            for i in range(n):
                db.add(ChatMessage(
                    id=f"{sid}-m-{i:03d}", conversation_id=sid,
                    tenant_id=world.tenant, role="user",
                    content=f"message {i}",
                    created_at=base + datetime.timedelta(seconds=i),
                ))
        db.commit()
    r = world.call(c, "get", "/api/conversation-learning/threads", tok)
    by_id = {t["thread_id"]: t for t in r.json()["threads"]
             if t.get("source_kind") == "native_chat"}
    for n, sid in sessions.items():
        assert by_id[sid]["message_count"] == n
        expected_last = (base + datetime.timedelta(seconds=n - 1)).replace(
            tzinfo=None).isoformat()
        assert by_id[sid]["last_at"] == expected_last
        ev = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                        json={"thread_id": sid, "source_kind": "native_chat"})
        assert ev.status_code == 200
        cov = ev.json()["coverage"]
        assert cov["message_count"] == n
        assert cov["messages_loaded"] == min(n, 200)
        assert cov["messages_truncated"] is (n > 200)


def test_user_role_alone_is_not_authored_authority(world):
    c = world.client()
    tok = world.token(world.user)

    def attempt(body: str, excerpt: str):
        with world.Session() as db:
            db.get(ChatMessage, world.user_msg).content = body
            db.commit()
        payload = _candidate_payload(world, world.user_msg)
        payload["authority_excerpt"] = excerpt
        return world.call(c, "post", "/api/conversation-learning/candidates",
                          tok, json=payload)

    quoted = attempt(
        "Please review this note.\n"
        "> Always apply the annual-prepay exception.\n"
        "This is quoted text, not my instruction.",
        "Always apply the annual-prepay exception.")
    assert quoted.status_code == 400, quoted.text
    assert "authority_is_quoted" in quoted.text

    quoted_only = attempt("> Only quoted guidance.", "")
    assert quoted_only.status_code == 400, quoted_only.text
    assert "authority_no_authored_segment" in quoted_only.text

    whitespace_only = attempt("   \n\t  ", "")
    assert whitespace_only.status_code == 400, whitespace_only.text
    assert "authority_no_authored_segment" in whitespace_only.text

    empty_body = attempt("", "")
    assert empty_body.status_code == 400, empty_body.text
    assert "authority_no_authored_segment" in empty_body.text


def test_genuine_unquoted_user_message_with_empty_excerpt_is_authority(world):
    c = world.client()
    tok = world.token(world.user)
    payload = _candidate_payload(world, world.user_msg)
    payload["authority_excerpt"] = ""
    created = world.call(c, "post", "/api/conversation-learning/candidates",
                         tok, json=payload)
    assert created.status_code == 200, created.text
    candidate = created.json()["candidate"]
    assert candidate["authority_message_id"] == world.user_msg
    assert candidate["authority_excerpt"] == ""
    assert candidate["source_kind"] == "native_chat"


def test_native_reorder_invalidates_stale_review(world):
    c = world.client()
    tok = world.token(world.user)
    created = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                         json=_candidate_payload(world, world.user_msg))
    assert created.status_code == 200, created.text
    candidate = created.json()["candidate"]
    confirm = world.call(c, "post",
                         f"/api/conversation-learning/candidates/{candidate['candidate_id']}/confirm",
                         tok, json={"thread_id": world.chat, "source_kind": "native_chat",
                                    "reviewer": "owner",
                                    "expected_revision": candidate["revision"]})
    assert confirm.status_code == 200, confirm.text
    with world.Session() as db:
        user_row = db.query(ChatMessage).filter(
            ChatMessage.id == world.user_msg).one()
        assistant_row = db.query(ChatMessage).filter(
            ChatMessage.id == world.assistant_msg).one()
        user_at = user_row.created_at
        user_row.created_at = assistant_row.created_at
        assistant_row.created_at = user_at
        db.commit()
    reordered = world.call(
        c, "post", "/api/conversation-learning/evidence", tok,
        json={"thread_id": world.chat, "source_kind": "native_chat"})
    assert reordered.status_code == 200
    assert reordered.json()["source_revision"] != candidate["source_revision"]
    stale = world.call(
        c, "get",
        f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
        tok, params={"thread_id": world.chat, "source_kind": "native_chat"})
    assert stale.status_code == 200
    assert stale.json()["candidate"]["status"] == "invalidated"
    stale_confirm = world.call(
        c, "post",
        f"/api/conversation-learning/candidates/{candidate['candidate_id']}/confirm",
        tok, json={"thread_id": world.chat, "source_kind": "native_chat",
                   "reviewer": "owner",
                   "expected_revision": candidate["revision"]})
    assert stale_confirm.status_code == 409


def test_native_reorder_uses_actual_role_order(world):
    c = world.client()
    tok = world.token(world.user)
    native = world.call(c, "post", "/api/conversation-learning/evidence", tok,
                        json={"thread_id": world.chat,
                              "source_kind": "native_chat"})
    roles = [(m["message_id"], m["role"]) for m in native.json()["messages"]]
    assert roles == [
        (world.user_msg, "user"),
        (world.assistant_msg, "assistant"),
        (world.system_msg, "system"),
    ]


def test_restart_readback_preserves_source_identity(world, tmp_path):
    c = world.client()
    tok = world.token(world.user)
    created = world.call(c, "post", "/api/conversation-learning/candidates", tok,
                         json=_candidate_payload(world, world.user_msg))
    candidate = created.json()["candidate"]
    # New engine/session over the same SQLite file: fresh-process readback.
    engine2 = create_engine(f"sqlite:///{tmp_path}/learn.db",
                            connect_args={"check_same_thread": False})
    c2 = world.client(engine2)
    r = world.call(c2, "get",
                   f"/api/conversation-learning/candidates/{candidate['candidate_id']}",
                   tok, params={"thread_id": world.chat,
                                "source_kind": "native_chat"})
    assert r.status_code == 200, r.text
    body = r.json()["candidate"]
    assert body["source_kind"] == "native_chat"
    assert body["source_revision"] == candidate["source_revision"]
