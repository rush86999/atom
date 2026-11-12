"""Offline regression for reviewed conversation-learning configuration writes.

The documented lifecycle is review-bound: a candidate is not permission to
write anything, ``confirm`` binds the exact current revision/digest, and
``promote`` is the only path that appends a standing lesson to
``AgentRegistry.configuration["learning"]["log"]``.  The write is scoped to
the candidate's tenant/workspace/agent and survives a fresh engine/session.

These tests drive the real mounted router with real JWT dependencies (only
``get_db`` points at scratch SQLite) and never touch the live dev DB, a model,
a provider or the network.
"""
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
    AgentRegistry,
    ChatMessage,
    ChatSession,
    ConversationEvent,
    Tenant,
    User,
    Workspace,
)


ORIGINAL_CONFIG = {"system_prompt": "keep", "tool_policy": {"mode": "safe"}}
LESSON = "Always cite the invoice number before quoting a price."


class World:
    def __init__(self, tmp_path):
        self.path = tmp_path / "reviewed-learning.db"
        self.engine = create_engine(
            f"sqlite:///{self.path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        suffix = uuid.uuid4().hex[:8]
        self.tenant = f"tenant-rl-{suffix}"
        self.workspace = f"ws-rl-{suffix}"
        self.foreign_tenant = f"tenant-foreign-rl-{suffix}"
        self.foreign_workspace = f"ws-foreign-rl-{suffix}"
        self.owner = f"user-rl-{suffix}"
        self.owner_email = f"owner-{suffix}@example.invalid"
        self.peer = f"user-peer-rl-{suffix}"
        self.foreign_user = f"user-foreign-rl-{suffix}"
        self.agent = f"agent-rl-{suffix}"
        self.sibling_agent = f"agent-sibling-rl-{suffix}"
        self.chat = f"chat-rl-{suffix}"
        self.message = f"msg-rl-{suffix}"
        now = datetime.datetime.now(datetime.timezone.utc)
        with self.Session() as db:
            db.add_all([
                Tenant(id=self.tenant, name="RL", subdomain=f"rl-{suffix}",
                       edition="personal", is_active=True),
                Workspace(id=self.workspace, name="RL Workspace",
                          tenant_id=self.tenant),
                Tenant(id=self.foreign_tenant, name="Foreign",
                       subdomain=f"frl-{suffix}", edition="personal",
                       is_active=True),
                Workspace(id=self.foreign_workspace, name="Foreign Workspace",
                          tenant_id=self.foreign_tenant),
            ])
            db.add_all([
                User(id=self.owner, tenant_id=self.tenant,
                     email=self.owner_email,
                     first_name="Owner", last_name="Reviewer", role="member",
                     status="active", workspace_id=self.workspace,
                     is_active=True),
                User(id=self.peer, tenant_id=self.tenant,
                     email=f"peer-{suffix}@example.invalid",
                     first_name="Peer", last_name="Member", role="member",
                     status="active", workspace_id=self.workspace,
                     is_active=True),
                User(id=self.foreign_user,
                     tenant_id=self.foreign_tenant,
                     email=f"foreign-{suffix}@example.invalid",
                     first_name="Foreign", last_name="Member", role="member",
                     status="active", workspace_id=self.foreign_workspace,
                     is_active=True),
            ])
            db.add_all([
                AgentRegistry(
                    id=self.agent, name="Reviewed Learning Agent",
                    category="sales", role="agent", type="personal",
                    capabilities=[], module_path="core.generic_agent",
                    class_name="GenericAgent", user_id=self.owner,
                    workspace_id=self.workspace, tenant_id=self.tenant,
                    status="autonomous", enabled=True,
                    configuration=dict(ORIGINAL_CONFIG)),
                AgentRegistry(
                    id=self.sibling_agent, name="Sibling Agent",
                    category="sales", role="agent", type="personal",
                    capabilities=[], module_path="core.generic_agent",
                    class_name="GenericAgent", user_id=self.owner,
                    workspace_id=self.workspace, tenant_id=self.tenant,
                    status="autonomous", enabled=True,
                    configuration=dict(ORIGINAL_CONFIG)),
                ChatSession(id=self.chat, user_id=self.owner,
                            title="Reviewed learning", message_count=1,
                            created_at=now, updated_at=now),
            ])
            db.flush()
            db.add(ChatMessage(
                id=self.message, conversation_id=self.chat,
                tenant_id=self.tenant, role="user", content=LESSON,
                created_at=now))
            db.commit()

    def token(self, user_id):
        with self.Session() as db:
            user = db.query(User).filter(User.id == user_id).one()
            return create_access_token({"sub": user.id}, user=user)

    def client(self):
        app = FastAPI()
        app.include_router(router)

        def override():
            session = self.Session()
            try:
                yield session
            finally:
                session.close()

        app.dependency_overrides[get_db] = override
        return TestClient(app, base_url="http://testserver")

    @staticmethod
    def call(client, method, path, token=None, **kwargs):
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return getattr(client, method)(path, headers=headers, **kwargs)

    def configuration(self, agent_id):
        with self.Session() as db:
            row = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id).one()
            return row.configuration

    def durable_configuration(self, agent_id):
        """Read through a brand-new engine, not the request's session."""
        fresh_engine = create_engine(f"sqlite:///{self.path}")
        Session = sessionmaker(bind=fresh_engine, expire_on_commit=False)
        try:
            with Session() as db:
                row = db.query(AgentRegistry).filter(
                    AgentRegistry.id == agent_id).one()
                return row.configuration
        finally:
            fresh_engine.dispose()

    def promoted_events(self, candidate_id):
        fresh_engine = create_engine(f"sqlite:///{self.path}")
        Session = sessionmaker(bind=fresh_engine, expire_on_commit=False)
        try:
            with Session() as db:
                rows = db.query(ConversationEvent).filter(
                    ConversationEvent.conversation_id == self.chat,
                    ConversationEvent.kind == "learning_candidate_promoted",
                ).order_by(ConversationEvent.created_at.asc()).all()
                return [
                    json.loads(row.payload_json or "{}") for row in rows
                    if str((json.loads(row.payload_json or "{}").get(
                        "candidate") or {}).get("candidate_id")) == str(
                            candidate_id)
                ]
        finally:
            fresh_engine.dispose()


@pytest.fixture()
def world(tmp_path):
    return World(tmp_path)


def _payload(world):
    return {
        "thread_id": world.chat,
        "source_kind": "native_chat",
        "agent_id": world.agent,
        "proposed_lesson": LESSON,
        "applies_to": ["pricing"],
        "context": {},
        "method_status": "not_applicable",
        "authority_message_id": world.message,
        "authority_excerpt": "Always cite the invoice number",
    }


def _create_candidate(world):
    with world.client() as client:
        response = world.call(
            client, "post", "/api/conversation-learning/candidates",
            world.token(world.owner), json=_payload(world))
    assert response.status_code == 200, response.text
    return response.json()


def _promote_body(created):
    return {
        "thread_id": created["candidate"]["thread_id"],
        "source_kind": created["candidate"]["source_kind"],
        "reviewer": "forged-reviewer",
        "expected_revision": created["candidate"]["revision"],
        "expected_digest": created["review"]["digest"],
    }


def test_unreviewed_and_foreign_requests_do_not_mutate_configuration(world):
    created = _create_candidate(world)
    assert created["review_ready"] is True, created
    body = _promote_body(created)
    candidate_id = created["candidate"]["candidate_id"]

    with world.client() as client:
        unreviewed = world.call(
            client, "post",
            f"/api/conversation-learning/candidates/{candidate_id}/promote",
            world.token(world.owner), json=body)
        unauthenticated = client.get(
            f"/api/conversation-learning/candidates/{candidate_id}",
            params={"thread_id": world.chat, "source_kind": "native_chat"})
        foreign_promote = world.call(
            client, "post",
            f"/api/conversation-learning/candidates/{candidate_id}/promote",
            world.token(world.foreign_user), json=body)
        foreign_read = world.call(
            client, "get",
            f"/api/conversation-learning/candidates/{candidate_id}",
            world.token(world.foreign_user),
            params={"thread_id": world.chat, "source_kind": "native_chat"})
        peer_promote = world.call(
            client, "post",
            f"/api/conversation-learning/candidates/{candidate_id}/promote",
            world.token(world.peer), json=body)

    # Review is not optional: the exact pending snapshot is refused.
    assert unreviewed.status_code == 409, unreviewed.text
    assert "candidate_not_confirmed" in unreviewed.text
    # The normal JWT dependency rejects a missing token.
    assert unauthenticated.status_code == 401, unauthenticated.text
    # Candidate access is owner/tenant/workspace scoped: no read, no write.
    assert foreign_read.status_code == 404, foreign_read.text
    assert foreign_promote.status_code == 404, foreign_promote.text
    assert peer_promote.status_code == 404, peer_promote.text

    assert world.configuration(world.agent) == ORIGINAL_CONFIG
    assert world.durable_configuration(world.agent) == ORIGINAL_CONFIG
    assert world.promoted_events(candidate_id) == []


def test_confirmed_promotion_writes_scoped_configuration_durably(world):
    created = _create_candidate(world)
    assert created["review_ready"] is True, created
    candidate_id = created["candidate"]["candidate_id"]
    body = _promote_body(created)

    with world.client() as client:
        confirmed = world.call(
            client, "post",
            f"/api/conversation-learning/candidates/{candidate_id}/confirm",
            world.token(world.owner), json=body)
    assert confirmed.status_code == 200, confirmed.text
    confirmed_body = confirmed.json()
    # The reviewer identity comes from authentication, not the request body.
    assert confirmed_body["candidate"]["confirmed_by"] == world.owner_email

    promote_body = {
        "thread_id": world.chat,
        "source_kind": "native_chat",
        "reviewer": "forged-reviewer",
        "expected_revision": confirmed_body["candidate"]["revision"],
        "expected_digest": confirmed_body["review"]["digest"],
    }
    with world.client() as client:
        promoted = world.call(
            client, "post",
            f"/api/conversation-learning/candidates/{candidate_id}/promote",
            world.token(world.owner), json=promote_body)
    assert promoted.status_code == 200, promoted.text
    promoted_body = promoted.json()
    lesson_id = promoted_body["lesson_id"]
    assert lesson_id
    assert promoted_body["candidate"]["status"] == "promoted"

    # Durable mutation: a brand-new engine sees the same standing lesson.
    config = world.durable_configuration(world.agent)
    assert config["system_prompt"] == ORIGINAL_CONFIG["system_prompt"]
    assert config["tool_policy"] == ORIGINAL_CONFIG["tool_policy"]
    log = config["learning"]["log"]
    assert len(log) == 1
    entry = log[0]
    assert entry["id"] == lesson_id
    assert entry["lesson"] == LESSON
    assert entry["source"] == "teacher"
    assert entry["workspace_id"] == world.workspace
    provenance = entry["details"]["conversation_learning"]
    assert provenance["candidate_id"] == candidate_id
    assert provenance["agent_id"] == world.agent
    assert provenance["workspace_id"] == world.workspace
    assert provenance["tenant_id"] == world.tenant
    assert provenance["source_kind"] == "native_chat"
    assert provenance["digest"] == confirmed_body["review"]["digest"]

    # The mutation is bound to the target agent only.
    assert world.durable_configuration(world.sibling_agent) == ORIGINAL_CONFIG

    # The reviewed lesson is also readable through the normal work-time
    # consumer in that fresh session.
    from core.student_learning_service import get_agent_lessons

    fresh_engine = create_engine(f"sqlite:///{world.path}")
    Session = sessionmaker(bind=fresh_engine, expire_on_commit=False)
    try:
        with Session() as db:
            lessons = get_agent_lessons(
                db, world.agent, include_workspace=False,
                workspace_id=world.workspace)
    finally:
        fresh_engine.dispose()
    assert [item.get("lesson") for item in lessons] == [LESSON]

    # The append-only candidate ledger records the promotion durably.
    events = world.promoted_events(candidate_id)
    assert len(events) == 1
    assert events[0]["candidate"]["status"] == "promoted"
    assert events[0]["candidate"]["promoted_entry_id"] == lesson_id
