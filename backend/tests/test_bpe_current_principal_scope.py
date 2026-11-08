"""Current-principal BPE workspace scope contract (Phase 1).

The confirmed defect: ``POST /api/rpc/workspace.note`` supplied only
``user``/``user_id``/``db``, while the BPE handlers read ``workspace_id`` /
``agent_id`` / ``session_id`` from the dispatch context. All authenticated
RPC callers therefore appended to the same ``("default", "atom_main", "")``
buffer.

These twins pin the repaired contract on real SQLite rows and the real
mounted RPC router:

- a real actor keeps their own buffer across calls;
- a peer (different workspace *or* a NULL/Personal default principal) never
  inherits it;
- caller body params can never grant a namespace;
- a missing/inactive principal, or an authority change after a stale read,
  fails closed with a typed no-effect (no append);
- the Generic/MCP server-bound context stays workable and is the same
  namespace the prompt/close-out use;
- bare/shared anonymous defaults are refused.

No live model/provider/server or production DB is used.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def actors(tmp_path, monkeypatch):
    """Real Tenant/Workspace/User rows + a mounted RPC app."""
    import core.models  # noqa: F401 — model registration side effect
    from core.models_registration import Base
    from core.models import Tenant, User, Workspace
    from core.bpe import persistence, workspace
    from api.rpc_routes import router as rpc_router
    from core.auth import get_current_user
    from core.database import get_db

    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path / "bpe")
    workspace.reset_registry()

    engine = create_engine(
        "sqlite:///" + str(tmp_path / "actors.db"),
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as s:
        s.add(Tenant(id="bpe-tenant", name="scratch", subdomain="bpe-scratch"))
        s.commit()
        for label in ("a", "b", "mcp"):
            s.add(Workspace(id=f"bpe-ws-{label}", name=f"scratch-{label}",
                            tenant_id="bpe-tenant"))
        s.commit()
        # a/b live in distinct workspaces; c/d are the single-tenant Personal
        # (NULL workspace) default; e is inactive; ghost has no row at all.
        for label in ("a", "b"):
            s.add(User(
                id=f"bpe-user-{label}", email=f"{label}@bpe.example.invalid",
                first_name="Probe", last_name=label, role="member",
                status="active", is_active=True, tenant_id="bpe-tenant",
                workspace_id=f"bpe-ws-{label}",
            ))
        for label in ("c", "d"):
            s.add(User(
                id=f"bpe-user-{label}", email=f"{label}@bpe.example.invalid",
                first_name="Personal", last_name=label, role="member",
                status="active", is_active=True, tenant_id="bpe-tenant",
                workspace_id=None,
            ))
        # Literal single-tenant ``default`` without a workspaces row.
        for label in ("f", "g"):
            s.add(User(
                id=f"bpe-user-{label}", email=f"{label}@bpe.example.invalid",
                first_name="Default", last_name=label, role="member",
                status="active", is_active=True, tenant_id="bpe-tenant",
                workspace_id="default",
            ))
        s.add(User(
            id="bpe-user-e", email="e@bpe.example.invalid", first_name="Inactive",
            last_name="Probe", role="member", status="suspended",
            is_active=False, tenant_id="bpe-tenant", workspace_id="bpe-ws-a",
        ))
        s.commit()
    workspace.reset_registry()

    actor = {"id": "bpe-user-a"}

    def _current():
        with Session() as s:
            row = s.get(User, actor["id"])
            if row is not None:
                return row
        # A deactivated/deleted account dependency can still hand back an
        # identity object; the handler must re-read and refuse it.
        return SimpleNamespace(
            id=actor["id"], workspace_id=None, status="active", is_active=True,
        )

    def _db():
        with Session() as s:
            yield s

    app = FastAPI()
    app.include_router(rpc_router)
    app.dependency_overrides[get_current_user] = _current
    app.dependency_overrides[get_db] = _db
    client = TestClient(app)

    yield SimpleNamespace(
        client=client, actor=actor, Session=Session, engine=engine,
        workspace=workspace,
    )
    workspace.reset_registry()
    engine.dispose()


def _post_note(actors, params: dict, actor_id: str = "bpe-user-a"):
    actors.actor["id"] = actor_id
    return actors.client.post("/api/rpc/workspace.note", json={"params": params})


def _snapshot(actors, workspace_id, agent_id="atom_main", scope_key=""):
    return actors.workspace.get_workspace_snapshot(
        workspace_id, agent_id, scope_key)


# ---------------------------------------------------------------------------
# RPC: real principal rows
# ---------------------------------------------------------------------------


def test_same_actor_continues_own_buffer(actors):
    one = _post_note(actors, {"content": "first owned note"})
    two = _post_note(actors, {"content": "second owned note"})
    assert one.status_code == two.status_code == 200, (one.text, two.text)
    assert one.json()["success"] is True
    assert one.json()["data"]["buffered"] == 1
    assert two.json()["data"]["buffered"] == 2

    snap = _snapshot(actors, "bpe-ws-a", scope_key="user:bpe-user-a")
    assert snap is not None
    assert len(snap["pending_notes"]) == 2


def test_tampered_body_params_cannot_grant_namespace(actors):
    resp = _post_note(actors, {
        "content": "owned by a",
        # All of these are data, not identity: the authenticated row wins.
        "user_id": "bpe-user-b",
        "workspace_id": "bpe-ws-b",
        "tenant_id": "peer-tenant",
        "agent_id": "peer-agent",
        "session_id": "peer-session",
    })
    assert resp.status_code == 200
    assert resp.json()["data"]["buffered"] == 1

    assert _snapshot(actors, "bpe-ws-a", scope_key="user:bpe-user-a") is not None
    assert _snapshot(actors, "bpe-ws-b") is None
    assert _snapshot(actors, "bpe-ws-b", scope_key="user:bpe-user-b") is None
    assert _snapshot(actors, "default") is None


def test_different_workspace_principal_never_inherits_peer_buffer(actors):
    a = _post_note(actors, {"content": "workspace A private insight"},
                   actor_id="bpe-user-a")
    assert a.json()["data"]["buffered"] == 1
    b = _post_note(actors, {"content": "workspace B private insight"},
                   actor_id="bpe-user-b")
    assert b.status_code == 200
    assert b.json()["data"]["buffered"] == 1

    other = _snapshot(actors, "bpe-ws-b", scope_key="user:bpe-user-b")
    assert len(other["pending_notes"]) == 1
    assert other["pending_notes"] == ["workspace B private insight"]


def test_personal_null_workspace_principals_are_isolated(actors):
    c = _post_note(actors, {"content": "c private note"}, actor_id="bpe-user-c")
    d = _post_note(actors, {"content": "d private note"}, actor_id="bpe-user-d")
    assert c.json()["data"]["buffered"] == 1
    assert d.json()["data"]["buffered"] == 1

    assert _snapshot(actors, "personal:bpe-user-c",
                     scope_key="user:bpe-user-c") is not None
    assert _snapshot(actors, "personal:bpe-user-d",
                     scope_key="user:bpe-user-d") is not None
    # The single-tenant Personal default is per-user — never a shared buffer.
    assert _snapshot(actors, "default") is None
    assert _snapshot(actors, "personal:bpe-user-c",
                     scope_key="user:bpe-user-d") is None


def test_literal_default_workspace_principals_are_isolated(actors):
    f = _post_note(actors, {"content": "f default note"}, actor_id="bpe-user-f")
    g = _post_note(actors, {"content": "g default note"}, actor_id="bpe-user-g")
    assert f.json()["data"]["buffered"] == 1
    assert g.json()["data"]["buffered"] == 1
    assert _snapshot(actors, "default", scope_key="user:bpe-user-f") is not None
    assert _snapshot(actors, "default", scope_key="user:bpe-user-g") is not None
    assert _snapshot(actors, "default", scope_key="") is None


def test_missing_principal_fails_closed_with_typed_no_effect(actors):
    resp = _post_note(actors, {"content": "should not land"},
                      actor_id="bpe-user-ghost")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False  # no success wrapper around a refusal
    assert body["data"]["success"] is False
    assert body["data"]["error"] == "scope_principal_missing"
    assert body["data"]["action_result"] == "not_applied"
    assert body["data"]["effect_possible"] is False
    assert _snapshot(actors, "default") is None


def test_inactive_principal_fails_closed(actors):
    resp = _post_note(actors, {"content": "should not land"},
                      actor_id="bpe-user-e")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["data"]["error"] == "scope_principal_inactive"
    assert body["data"]["action_result"] == "not_applied"
    assert _snapshot(actors, "bpe-ws-a", scope_key="user:bpe-user-e") is None


# ---------------------------------------------------------------------------
# Current-authority change / claim before append
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_authority_change_refuses_append(actors):
    from core.action_registry import action_registry
    from core.models import User

    with actors.Session() as db:
        db.execute(
            update(User)
            .where(User.id == "bpe-user-a")
            .values(workspace_id="bpe-ws-b")
        )
        db.commit()
        stale = SimpleNamespace(
            id="bpe-user-a", workspace_id="bpe-ws-a",
            status="active", is_active=True,
        )
        result = await action_registry.execute_action(
            "workspace.note", {"content": "stale authority"},
            {"user": stale, "user_id": "bpe-user-a", "db": db},
        )
    assert result["success"] is False
    assert result["error"] == "scope_authority_changed"
    assert result["action_result"] == "not_applied"
    assert _snapshot(actors, "bpe-ws-a", scope_key="user:bpe-user-a") is None
    assert _snapshot(actors, "bpe-ws-b", scope_key="user:bpe-user-a") is None


def test_claim_rechecks_workspace_before_append(actors):
    from core.bpe.actions import _claim_authority
    from core.models import User

    with actors.Session() as db:
        db.execute(
            update(User)
            .where(User.id == "bpe-user-a")
            .values(workspace_id="bpe-ws-b")
        )
        db.commit()
        denial = _claim_authority(
            {"db": db},
            {
                "authority": "user", "user_id": "bpe-user-a",
                "workspace_id": "bpe-ws-a", "workspace_claim": True,
            },
        )
    assert denial is not None
    assert denial["error"] == "scope_authority_changed"
    assert denial["action_result"] == "not_applied"


# ---------------------------------------------------------------------------
# Generic / MCP server-bound context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generic_server_scope_ignores_forged_params_and_matches_render(actors):
    """The GenericAgent dispatch path: caller params are not a namespace."""
    from core.bpe.actions import (
        PRINCIPAL_SCOPE_CONTEXT_KEY,
        bind_trusted_scope,
        bpe_scope_from_context,
    )
    from integrations.mcp_service import mcp_service

    # api/agent_routes.py passes request params as ``context`` — including a
    # forged reserved key, workspace, agent and session.
    context = {
        "workspace_id": "peer-ws",
        "agent_id": "peer-agent",
        "session_id": "peer-session",
        "user_id": "bpe-user-b",
        PRINCIPAL_SCOPE_CONTEXT_KEY: {
            "workspace_id": "peer-ws", "agent_id": "peer-agent",
            "scope_key": "peer-session",
        },
    }
    bind_trusted_scope(
        context, workspace_id="agent-ws", agent_id="agent-1",
        scope_key="server-run",
    )
    assert bpe_scope_from_context(context) == (
        "agent-ws", "agent-1", "server-run")

    result = await mcp_service.call_tool(
        "workspace.note", {"content": "generic-owned"}, context=context)
    assert result["success"] is True
    assert result["buffered"] == 1

    snap = _snapshot(actors, "agent-ws", agent_id="agent-1",
                     scope_key="server-run")
    assert snap["pending_notes"] == ["generic-owned"]
    assert _snapshot(actors, "peer-ws") is None
    assert _snapshot(actors, "default") is None


@pytest.mark.asyncio
async def test_mcp_current_context_uses_its_server_scope(actors):
    from integrations.mcp_service import mcp_service

    context = {
        "workspace_id": "bpe-ws-mcp", "agent_id": "mcp-agent",
        "session_id": "mcp-session",
    }
    one = await mcp_service.call_tool(
        "workspace.note", {"content": "mcp note 1"}, context=context)
    two = await mcp_service.call_tool(
        "workspace.note", {"content": "mcp note 2"}, context=context)
    assert one["buffered"] == 1 and two["buffered"] == 2

    peer = await mcp_service.call_tool(
        "workspace.note", {"content": "peer note"},
        context={"workspace_id": "bpe-ws-b", "agent_id": "mcp-agent",
                 "session_id": "mcp-session"},
    )
    assert peer["buffered"] == 1

    snap = _snapshot(actors, "bpe-ws-mcp", agent_id="mcp-agent",
                     scope_key="mcp-session")
    assert snap["pending_notes"] == ["mcp note 1", "mcp note 2"]


@pytest.mark.asyncio
async def test_all_four_actions_share_the_principal_scope(actors):
    from core.action_registry import action_registry
    from core.bpe.adapter import NullAdapter
    from core.bpe.workspace import get_workspace

    # Keep track on the deterministic null adapter (no GraphRAG/LLM call).
    get_workspace("bpe-ws-a", "atom_main", "user:bpe-user-a").adapter = NullAdapter()

    with actors.Session() as db:
        from core.models import User

        user = db.get(User, "bpe-user-a")
        context = {"user": user, "user_id": "bpe-user-a", "db": db}

        track = await action_registry.execute_action(
            "workspace.track", {"topic": "world"}, context)
        commit = await action_registry.execute_action(
            "workspace.commit", {"title": "scoped subgoal"}, context)
        recall = await action_registry.execute_action(
            "workspace.recall", {"query": "anything"}, context)
        note = await action_registry.execute_action(
            "workspace.note", {"content": "scoped note"}, context)

    assert track["success"] is True
    assert commit["success"] is True
    assert recall["success"] is True
    assert note["success"] is True

    snap = _snapshot(actors, "bpe-ws-a", scope_key="user:bpe-user-a")
    assert snap["progress"][0]["title"] == "scoped subgoal"
    assert snap["pending_notes"] == ["scoped note"]
    # No peer/default namespace was created by any of the four actions.
    assert _snapshot(actors, "default") is None
    assert _snapshot(actors, "bpe-ws-a", scope_key="") is None


@pytest.mark.asyncio
async def test_recall_does_not_cross_principal_namespaces(actors):
    from core.action_registry import action_registry
    from core.bpe.consolidation import consolidate_workspace_notes
    from core.bpe.workspace import get_workspace
    from core.models import User

    a_ws = get_workspace("bpe-ws-a", "atom_main", "user:bpe-user-a")
    a_ws._pending_notes.append("avoid the peer-only detail")
    consolidate_workspace_notes(a_ws)

    with actors.Session() as db:
        peer = db.get(User, "bpe-user-b")
        result = await action_registry.execute_action(
            "workspace.recall", {"query": "avoid peer-only detail"},
            {"user": peer, "user_id": "bpe-user-b", "db": db},
        )
    assert result["success"] is True
    assert result["results"] == []


@pytest.mark.asyncio
async def test_anonymous_default_scope_is_refused(actors):
    from core.action_registry import action_registry

    for context in ({}, {"workspace_id": "default"},
                    {"agent_id": "atom_main", "session_id": "s"}):
        result = await action_registry.execute_action(
            "workspace.note", {"content": "anonymous"}, context)
        assert result["success"] is False
        assert result["error"] == "scope_authority_missing"
        assert result["action_result"] == "not_applied"
    assert _snapshot(actors, "default") is None
