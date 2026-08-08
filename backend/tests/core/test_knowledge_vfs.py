"""
P2 — Knowledge VFS (W1): ls/cat/grep over IngestedDocument+KnowledgeDocument.

Verifies the agent-native virtual filesystem: line-numbered content.lines
(L<n>: <text>), precise grep citations, capability-resolved actions, and
kill-switch parity (flag off → disabled note).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.models import IngestedDocument, KnowledgeDocument, Tenant, Workspace


@pytest.fixture
def vfs_provider(monkeypatch):
    """Build a KnowledgeVFSProvider backed by an in-memory SQLite session."""
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed a tenant + workspace (FKs) + documents.
    session.add(Tenant(id="t1", name="t1", subdomain="t1"))
    session.add(Workspace(id="ws1", tenant_id="t1", name="ws1"))
    session.add(IngestedDocument(
        id="ing1", workspace_id="ws1", tenant_id="t1",
        file_name="budget.csv", file_path="/tmp/budget.csv", file_type="csv",
        integration_id="drive1", external_id="ext1",
        content_preview="Q1 revenue was high\nQ2 revenue was low\n",
    ))
    session.add(KnowledgeDocument(
        id="kd1", tenant_id="t1", workspace_id="ws1",
        title="Sales Notes", content="The pipeline grew 20%.\nChurn rose in Q3.\n",
        doc_type="text",
    ))
    session.commit()

    from integrations.vfs.knowledge_vfs import KnowledgeVFSProvider
    provider = KnowledgeVFSProvider(db_factory=lambda: Session(bind=engine))
    yield provider, session
    session.close()


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ls_root(vfs_provider):
    provider, _ = vfs_provider
    nodes = await provider.ls("knowledge")
    assert any(n.name == "documents" and n.type == "dir" for n in nodes)


@pytest.mark.asyncio
async def test_ls_documents_lists_seeded(vfs_provider):
    provider, _ = vfs_provider
    nodes = await provider.ls("knowledge/documents")
    names = {n.name for n in nodes}
    assert "ing1" in names and "kd1" in names


@pytest.mark.asyncio
async def test_ls_document_leaf(vfs_provider):
    provider, _ = vfs_provider
    nodes = await provider.ls("knowledge/documents/ing1")
    leaves = {n.name for n in nodes}
    assert "meta.json" in leaves and "content.lines" in leaves


# ---------------------------------------------------------------------------
# cat — line-numbered content
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cat_returns_line_numbered_content(vfs_provider):
    provider, _ = vfs_provider
    res = await provider.cat("knowledge/documents/ing1/content.lines")
    assert res.lines[0].startswith("L1: "), "content must be line-numbered L<n>: <text>"
    assert "revenue" in res.lines[0]
    assert res.meta["source"] == "ingested"
    assert res.meta["file_name"] == "budget.csv"


@pytest.mark.asyncio
async def test_cat_meta_json(vfs_provider):
    provider, _ = vfs_provider
    res = await provider.cat("knowledge/documents/kd1/meta.json")
    assert res.meta["source"] == "knowledge"
    assert res.meta["title"] == "Sales Notes"


# ---------------------------------------------------------------------------
# grep — precise citations
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_grep_returns_citations(vfs_provider):
    provider, _ = vfs_provider
    citations = await provider.grep("revenue", "knowledge/documents")
    assert len(citations) >= 1
    c = citations[0]
    assert c.path.startswith("knowledge/documents/")
    assert c.line >= 1
    assert "revenue" in c.snippet.lower() or "L" in c.snippet  # snippet from a line


# ---------------------------------------------------------------------------
# registered actions (kill-switch parity + flag-on behavior)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_action_ls_disabled_when_flag_off(monkeypatch):
    monkeypatch.delenv("ATOM_KNOWLEDGE_VFS_ENABLED", raising=False)
    from core.action_registry import action_registry
    res = await action_registry.execute_action("documents.ls", {"path": "knowledge"}, {})
    assert res["success"] is False and res["error"] == "vfs_disabled"


@pytest.mark.asyncio
async def test_action_ls_enabled(monkeypatch, vfs_provider):
    # Register the seeded provider so the action resolves to it.
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.ls", {"path": "knowledge/documents"}, {}
    )
    assert res["success"] is True
    names = {e["name"] for e in res["entries"]}
    assert "ing1" in names
