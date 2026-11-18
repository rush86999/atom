"""Production Chat document context for the installed bootstrap owner.

The RPC ``documents.search`` path resolves the authenticated principal's
trusted document scope and (for the server-owned bootstrap account) the
guarded legacy proof.  The ordinary Chat knowledge leg used to construct
``DocumentsHybridSearch`` with no scope at all, so the same authorized
document was invisible to Chat and no source observation was published.

These regressions go through the production seam: ``assemble_memory_context``
with a persisted user id, the real ``_knowledge_leg``, and a scratch
SQLite/LanceDB world.  No model provider, network, live database or owner
artifact is used.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

os.environ.setdefault("TESTING", "1")

import core.database as database
import core.lancedb_handler as storage
import core.memory_context_assembler as mca
from core.database import Base
from core.models import IngestedDocument, Tenant, User, Workspace


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """Scratch SQL + LanceDB world with the real bootstrap admin account."""
    monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path / "stores"))
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    monkeypatch.setenv("ATOM_BOOTSTRAP_PASSWORD_FILE", str(tmp_path / "pw"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    # Keep the knowledge leg's own contract under test; rerank/conversations
    # are separate lanes and are not needed to prove document scope.
    monkeypatch.setenv("MEMORY_CONTEXT_RERANK", "false")
    monkeypatch.setenv("MEMORY_CONVERSATIONS_LEG", "false")
    monkeypatch.setattr(storage, "_workspace_handlers", {})

    from core.embedding_service import EmbeddingService

    async def _deterministic_embedding(self, text):
        # Non-zero constant vector: cosine 1.0 for every text, so a vector
        # hit proves the STORE was read, not a lexical coincidence.
        return [0.03125] * 384

    monkeypatch.setattr(
        EmbeddingService, "generate_embedding", _deterministic_embedding)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'chat-scope-world.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(database, "engine", engine)

    # The real first-launch bootstrap path: NULL tenant/workspace scope.
    monkeypatch.setenv("ADMIN_PASSWORD", "synthetic-bootstrap-password")
    from core.admin_bootstrap import ensure_admin_user

    ensure_admin_user()
    with Session() as db:
        admin = db.query(User).filter(
            User.email == "admin@example.com").one()
        assert admin.workspace_id is None
        assert admin.tenant_id is None

    return SimpleNamespace(Session=Session, admin=admin)


def _add_member(world, workspace_id: str):
    tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
    user_id = f"member-{uuid.uuid4().hex[:8]}"
    with world.Session() as db:
        db.add(Tenant(id=tenant_id, name="Member tenant",
                      subdomain=f"member-{uuid.uuid4().hex[:8]}"))
        db.add(Workspace(id=workspace_id, name="Member workspace",
                         tenant_id=tenant_id))
        db.add(User(
            id=user_id, email=f"{user_id}@example.invalid",
            first_name="Member", last_name="User", role="member",
            status="active", is_active=True,
            tenant_id=tenant_id, workspace_id=workspace_id,
        ))
        db.commit()
    return user_id


def _add_unbound_member(world):
    user_id = f"unbound-{uuid.uuid4().hex[:8]}"
    with world.Session() as db:
        db.add(User(
            id=user_id, email=f"{user_id}@example.invalid",
            first_name="Unbound", last_name="User", role="member",
            status="active", is_active=True,
            tenant_id=None, workspace_id=None,
        ))
        db.commit()
    return user_id


def _seed_legacy_document(world, content: str, owner_id: str) -> str:
    """A pre-repair upload: vector row in the legacy shared namespace plus
    its authoritative fresh SQL mirror in the Personal workspace."""
    from core.doc_freshness_service import extraction_content_hash

    doc_id = f"legacy-{uuid.uuid4().hex[:12]}"
    revision = extraction_content_hash(content)
    handler = storage.get_lancedb_handler("default_shared")
    assert handler.add_document(
        table_name="documents",
        text=content,
        source="upload:legacy.txt",
        metadata={
            "title": "legacy.txt",
            "file_name": "legacy.txt",
            "file_type": "txt",
            "source": "upload",
            "source_type": "upload",
            "integration_id": "manual_upload",
            "doc_id": doc_id,
            "pg_document_id": doc_id,
            "source_content_hash": revision,
            "author": "legacy@example.invalid",
        },
        user_id=owner_id,
        workspace_id="default_shared",
        doc_id=doc_id,
        extra_columns={"freshness_status": "fresh"},
    ) is True
    with world.Session() as db:
        db.add(IngestedDocument(
            id=doc_id,
            workspace_id="default",
            tenant_id=None,
            file_name="legacy.txt",
            file_path="",
            file_type="txt",
            integration_id="manual_upload",
            external_id=f"upload_{doc_id}",
            content_preview=content[:500],
            source_content_hash=revision,
            freshness_status="fresh",
        ))
        db.commit()
    return doc_id


@contextmanager
def _isolate_other_legs():
    """Keep every non-knowledge leg out of the scratch world."""
    with patch.object(mca, "_graph_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_integration_records_leg",
                      AsyncMock(return_value=[])), \
         patch.object(mca, "_episodes_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_facts_leg", AsyncMock(return_value=[])), \
         patch.object(mca, "_lessons_leg", AsyncMock(return_value="")), \
         patch.object(mca, "_exchange_examples_leg",
                      AsyncMock(return_value=[])), \
         patch.object(mca, "_playbooks_leg", AsyncMock(return_value="")):
        yield


@pytest.mark.asyncio
async def test_bootstrap_legacy_document_reaches_chat_context_and_observation(
        world):
    content = (
        "Historical pilot notes: the archive recovery code is HARBOR-77.\n"
    )
    doc_id = await asyncio.to_thread(
        _seed_legacy_document, world, content, world.admin.id)
    observations = []

    with _isolate_other_legs():
        block = await mca.assemble_memory_context(
            "quarterly revenue projection",
            workspace_id="default",
            tenant_id="default",
            agent_id="atom_main",
            user_id=world.admin.id,
            source_observations_out=observations,
        )

    assert block is not None
    assert "RELATED KNOWLEDGE & CONVERSATIONS" in block
    assert "HARBOR-77" in block

    doc_observations = [
        o for o in observations if o.get("title") == "legacy.txt"]
    assert len(doc_observations) == 1, observations
    observation = doc_observations[0]
    # Attribution shape is preserved, and the trusted scope is the resolved
    # Personal workspace the legacy proof belongs to.
    assert observation["source"] == "ingested"
    assert observation["file_name"] == "legacy.txt"
    assert observation["workspace_id"] == "default"
    assert "HARBOR-77" in observation["excerpt"]
    assert set(observation) == {
        "source", "title", "file_name", "content_hash", "workspace_id",
        "excerpt", "requested_fields", "subjects", "field_associations",
        "supplied_fields",
    }
    # Reading is not writing: the vector row stays in the legacy namespace.
    assert storage.get_lancedb_handler("default_shared").get_document_by_id(
        "documents", doc_id) is not None
    assert storage.get_lancedb_handler("default").get_document_by_id(
        "documents", doc_id) is None


@pytest.mark.asyncio
async def test_unbound_account_fails_closed_on_documents_but_keeps_conversations(
        world):
    user_id = _add_unbound_member(world)
    observations = []

    class FakeHybrid:
        calls = []

        async def search(self, **kwargs):
            FakeHybrid.calls.append(kwargs)
            return {"results": [{
                "source": "communication",
                "title": "outlook — 2026-01-02",
                "preview": "authorized conversation content",
                "sender": "colleague@example.invalid",
                "as_of": "2026-01-02",
            }]}

    with _isolate_other_legs(), patch(
            "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
            FakeHybrid):
        block = await mca.assemble_memory_context(
            "what did my colleague say",
            workspace_id="default",
            tenant_id="default",
            agent_id="atom_main",
            user_id=user_id,
            source_observations_out=observations,
        )

    assert FakeHybrid.calls, "the knowledge leg must still run"
    call = FakeHybrid.calls[0]
    # No documented scope → no document store may be read.
    assert call["documents_allowed"] is False
    # Conversations stay authorized by the authenticated owner id.
    assert call["owner_user_id"] == user_id
    assert block is not None
    assert "authorized conversation content" in block
    assert any(
        o.get("source") == "communication" for o in observations), observations


@pytest.mark.asyncio
async def test_bound_member_document_reads_its_own_workspace(world):
    workspace_id = f"ws-member-{uuid.uuid4().hex[:8]}"
    user_id = _add_member(world, workspace_id)
    # The Chat turn's own workspace: the document scope is resolved from the
    # persisted member, not taken from this argument.
    chat_workspace_id = "default"
    observations = []

    captured = {}

    class FakeHybrid:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def search(self, **kwargs):
            captured["search"] = kwargs
            return {"results": [
                {
                    "source": "ingested",
                    "title": "member.txt",
                    "file_name": "member.txt",
                    "content_hash": "hash-member",
                    "preview": "member scoped document marker",
                },
                {
                    # Bridged comms record: conversations-only leg.
                    "source": "communication",
                    "title": "member conversation",
                    "file_name": "member conversation",
                    "content_hash": "hash-conversation",
                    "preview": "member chat conversation marker",
                    "legs": ["conversations"],
                },
            ]}

    with _isolate_other_legs(), patch(
            "core.hybrid_search.documents_hybrid.DocumentsHybridSearch",
            FakeHybrid):
        block = await mca.assemble_memory_context(
            "member document question",
            workspace_id=chat_workspace_id,
            tenant_id="default",
            agent_id="atom_main",
            user_id=user_id,
            source_observations_out=observations,
        )

    assert captured["workspace_id"] == workspace_id
    assert "legacy_authority" not in captured
    assert captured["search"]["owner_user_id"] == user_id
    assert block is not None and "member scoped document marker" in block
    assert "member chat conversation marker" in block

    by_title = {o["title"]: o for o in observations}
    # A document hit is attributed to the resolved document workspace; the
    # conversations hit stays with the original Chat turn's workspace.
    assert by_title["member.txt"]["workspace_id"] == workspace_id
    assert by_title["member conversation"]["workspace_id"] == chat_workspace_id
    assert by_title["member conversation"]["workspace_id"] != workspace_id


def test_warmup_knowledge_call_stays_unscoped(monkeypatch):
    calls = []

    async def fake_knowledge(message, workspace_id, owner_user_id=None,
                             source_observations_out=None):
        calls.append((message, workspace_id, owner_user_id))
        return []

    monkeypatch.setattr(mca, "_knowledge_leg", fake_knowledge)
    monkeypatch.setattr(mca, "_integration_records_leg",
                        AsyncMock(return_value=[]))
    monkeypatch.setattr(mca, "_facts_leg", AsyncMock(return_value=[]))
    monkeypatch.setattr(mca, "_probe_cross_encoder", AsyncMock(return_value=None))
    monkeypatch.setattr(mca, "_rerank_lines", AsyncMock(return_value=[]))

    asyncio.run(mca.warm("ws-warm"))

    assert calls == [("warmup", "ws-warm", None)]
