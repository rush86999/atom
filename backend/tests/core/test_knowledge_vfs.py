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
    # Flag now defaults ON; test the explicit-off kill path.
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "false")
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


# ---------------------------------------------------------------------------
# hybrid documents.search — kill-switch parity + filters/ranking when on
# ---------------------------------------------------------------------------
@pytest.fixture
def search_db(monkeypatch, vfs_provider):
    """Point the actions' get_db_session at the fixture's in-memory engine."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    import core.database
    monkeypatch.setattr(core.database, "get_db_session", lambda: Session())
    return Session, engine


@pytest.mark.asyncio
async def test_action_search_flag_off_is_legacy_parity(monkeypatch, search_db):
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "false")  # default now ON
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.search", {"query": "revenue"}, {}
    )
    assert res["success"] is True
    assert "hybrid" not in res, "flag-off path must be the exact legacy contract"


@pytest.mark.asyncio
async def test_action_search_flag_on_ranks_and_filters(monkeypatch, search_db):
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.search", {"query": "revenue", "source": "ingested"}, {}
    )
    assert res["success"] is True
    assert res["hybrid"] == "lexical_ranked"


@pytest.mark.asyncio
async def test_search_filters_by_source_with_seeded_docs(monkeypatch, search_db, vfs_provider):
    """Hybrid path filters ingested vs knowledge stores independently."""
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "true")
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])

    Session, engine = search_db
    from core.models import IngestedDocument, KnowledgeDocument, Tenant, Workspace
    from core.action_registry import action_registry
    with Session() as db:
        db.add(Tenant(id="t1", name="t1", subdomain="t1"))
        db.add(Workspace(id="ws1", tenant_id="t1", name="ws1"))
        db.add(IngestedDocument(
            id="ing1", workspace_id="ws1", tenant_id="t1",
            file_name="budget.csv", file_path="/tmp/budget.csv",
            file_type="csv", integration_id="drive1", external_id="ext1",
            content_preview="Q1 revenue was high\nQ2 revenue was low\n",
        ))
        db.add(KnowledgeDocument(
            id="kd1", tenant_id="t1", workspace_id="ws1",
            title="Sales Notes", content="The pipeline grew 20%.\nChurn rose in Q3.\n",
        ))
        db.commit()
    res = await action_registry.execute_action(
        "documents.search", {"query": "revenue", "source": "ingested"}, {}
    )
    assert res["success"] is True
    sources = {r["source"] for r in res["results"]}
    assert sources == {"ingested"}, "source filter must exclude knowledge results"
    res2 = await action_registry.execute_action(
        "documents.search", {"query": "grew", "source": "knowledge"}, {}
    )
    assert res2["results"], "knowledge leg must find content match"


# ---------------------------------------------------------------------------
# tree / head / tail / scan — composition over ls/cat
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_action_tree(monkeypatch, vfs_provider):
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.tree", {"path": "knowledge/documents"}, {}
    )
    assert res["success"] is True
    assert any("ing1" in line for line in res["tree"])


@pytest.mark.asyncio
async def test_action_head_tail(monkeypatch, vfs_provider):
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    head = await action_registry.execute_action(
        "documents.head",
        {"path": "knowledge/documents/ing1/content.lines", "lines": 1}, {},
    )
    assert head["success"] is True
    assert head["head"] == ["L1: Q1 revenue was high"]
    tail = await action_registry.execute_action(
        "documents.tail",
        {"path": "knowledge/documents/ing1/content.lines", "lines": 2}, {},
    )
    assert tail["tail"][-2] == "L2: Q2 revenue was low"


@pytest.mark.asyncio
async def test_action_scan(monkeypatch, vfs_provider):
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.scan", {"path": "knowledge/documents"}, {}
    )
    assert res["success"] is True
    paths = {f["path"] for f in res["files"]}
    assert "knowledge/documents/ing1/meta.json" in paths
    assert "knowledge/documents/kd1/content.lines" in paths


# ---------------------------------------------------------------------------
# map / reduce — bounded fan-out + aggregation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_action_map_reduce(monkeypatch, vfs_provider):
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    mapped = await action_registry.execute_action(
        "documents.map",
        {
            "paths": [
                "knowledge/documents/ing1/content.lines",
                "knowledge/documents/kd1/content.lines",
            ],
            "op": "head",
            "lines": 1,
        }, {},
    )
    assert mapped["success"] is True
    assert mapped["items_processed"] == 2
    assert mapped["results"][0]["lines"]
    reduced = await action_registry.execute_action(
        "documents.reduce", {"items": mapped["results"], "mode": "count"}, {}
    )
    assert reduced["success"] is True
    assert reduced["total_lines"] == 2


@pytest.mark.asyncio
async def test_new_actions_disabled_when_flag_off(monkeypatch):
    monkeypatch.setenv("ATOM_KNOWLEDGE_VFS_ENABLED", "false")  # default now ON
    from core.action_registry import action_registry
    for name, args in [
        ("documents.tree", {"path": "knowledge"}),
        ("documents.head", {"path": "knowledge/documents/ing1/content.lines"}),
        ("documents.tail", {"path": "knowledge/documents/ing1/content.lines"}),
        ("documents.scan", {"path": "knowledge/documents"}),
        ("documents.map", {"paths": ["knowledge"], "op": "cat"}),
        ("documents.reduce", {"items": [], "mode": "count"}),
        ("documents.ask_image", {"path": "knowledge/documents/ing1/content.lines", "prompt": "what?"}),
    ]:
        res = await action_registry.execute_action(name, args, {})
        assert res["success"] is False and res["error"] == "vfs_disabled", name


@pytest.mark.asyncio
async def test_ask_image_degrades_when_provider_lacks_vision(vfs_provider):
    from core.vfs_registry import register_provider, get_provider
    if get_provider("knowledge") is None:
        register_provider(vfs_provider[0])
    from core.action_registry import action_registry
    res = await action_registry.execute_action(
        "documents.ask_image",
        {"path": "knowledge/documents/ing1/meta.json", "prompt": "what is shown?"}, {},
    )
    assert res["success"] is False
    assert res["error"] == "vision_unavailable"


@pytest.mark.asyncio
async def test_canvas_read_registered_and_requires_auth(monkeypatch):
    """P2c insertion must not have broken the canvas.read action."""
    from core.action_registry import action_registry
    res = await action_registry.execute_action("canvas.read", {"canvas_id": "c1"}, {})
    assert res["success"] is False
    assert "Authenticated user" in res.get("error", "")
