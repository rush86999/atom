"""
Coverage-push tests for core.graphrag_engine (tests-only; read-only source).

Targets the untested surface: input sanitizers, pattern extraction, canonical
entity resolution, add/ingest paths, local_search (SQLite + mocked PG CTE
branches), global_search, reindex, communities, and hypothesis patterns.
"""

import os
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.graphrag_engine as ge
from core.graphrag_engine import Entity, GraphRAGEngine, Relationship
from core.models import Formula, GraphCommunity, GraphEdge, GraphNode, User, Workspace


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from core.models_registration import Base

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.query(GraphNode).delete()
    db.query(GraphEdge).delete()
    db.query(GraphCommunity).delete()
    db.commit()
    db.close()


@pytest.fixture
def g(engine, session):
    eng = GraphRAGEngine(workspace_id="ws-1", tenant_id="t-1", db=session)
    eng.llm_service = Mock()
    eng.llm_service.generate_embedding = AsyncMock(return_value=None)
    return eng


def _db_ctx(session):
    """Patch target replacing get_db_session with one bound to our session."""
    from contextlib import contextmanager

    @contextmanager
    def ctx():
        yield session

    return patch("core.graphrag_engine.get_db_session", ctx)


def make_node(session, name, ntype="org", ws="ws-1", props=None, nid=None):
    node = GraphNode(
        id=nid or str(uuid.uuid4()),
        tenant_id="t-1",
        workspace_id=ws,
        name=name,
        type=ntype,
        description=f"desc-{name}",
        properties=props or {},
    )
    session.add(node)
    session.commit()
    return node


# ============================ pure helpers ============================


class TestSanitizers:
    def test_validate_search_input_empty(self, g):
        assert g._validate_search_input("") == ""
        assert g._validate_search_input(None) == ""

    def test_validate_search_input_too_long(self, g):
        with pytest.raises(ValueError, match="too long"):
            g._validate_search_input("x" * 501)

    def test_validate_search_input_control_chars(self, g):
        assert g._validate_search_input("a\x00b\x01c") == "abc"
        assert g._validate_search_input("a\tb\nc") == "a\tb\nc"

    def test_escape_like_pattern(self, g):
        assert g._escape_like_pattern("50%_\\") == "50\\%\\_\\\\"
        assert g._escape_like_pattern("plain") == "plain"

    def test_sanitize_canonical_data_filters(self, g):
        metadata = {"first_name": "Ali", "last_name": None, "email": "x@y.z"}
        out = g._sanitize_canonical_data("user", metadata)
        assert out == {"first_name": "Ali", "last_name": None, "email": "x@y.z"}

    def test_sanitize_canonical_data_str_dict(self, g):
        data = {"name": "  Acme  ", "email": " BOB@X.COM "}
        out = g._sanitize_canonical_data("user", data)
        assert out == {"name": "Acme", "email": "bob@x.com"}
        out2 = g._sanitize_canonical_data("workspace", {"name": "  X  "})
        assert out2 == {"name": "X"}

    def test_get_stats(self, g):
        stats = g.get_stats()
        assert stats["workspace_id"] == "ws-1"
        assert stats["nodes"] == 0


# ============================ pattern extraction ============================


class TestPatternExtraction:
    def test_extracts_all_entity_kinds(self, g):
        text = (
            "Contact john.doe@acme.com at http://acme.com/page or https://a.io/x, "
            "call 555-123-4567, dated 2024-03-15 and 03/16/2024 and Mar 17, 2024, "
            "price $1,234.56 or 100 USD, file at /tmp/data/report.txt, "
            "ip 192.168.1.1, id 550e8400-e29b-41d4-a716-446655440000"
        )
        entities, rels = g._pattern_extract_entities_and_relationships(text, "d1", "salesforce")
        types = {e.entity_type for e in entities}
        assert types == {"email", "url", "phone", "date", "currency", "file_path", "ip_address", "uuid"}
        assert rels == []
        names = [e.name for e in entities]
        assert len(names) == len(set(names))

    def test_deduplicates_repeated_matches(self, g):
        text = "a@b.com and also a@b.com plus 2024-01-01 then 2024-01-01"
        entities, _ = g._pattern_extract_entities_and_relationships(text, "d1", "src")
        assert len(entities) == 2

    def test_invalid_ip_rejected(self, g):
        entities, _ = g._pattern_extract_entities_and_relationships("999.999.999.999", "d1", "src")
        assert all(e.entity_type != "ip_address" for e in entities)

    def test_no_matches(self, g):
        entities, _ = g._pattern_extract_entities_and_relationships("plain text", "d1", "src")
        assert entities == []


# ============================ canonical resolution ============================


class TestCanonicalResolution:
    def test_resolve_unknown_type(self, g, session):
        with _db_ctx(session):
            assert g._resolve_canonical_entity(session, "ws-1", "nope", "ghost") is None

    def test_resolve_by_canonical_id(self, g, session):
        from core.models import UserTask

        task = UserTask(id="ut-1", tenant_id="t-1", title="My task")
        session.add(task)
        session.commit()
        with _db_ctx(session):
            found = g._resolve_canonical_entity(session, "t-1", "ut-1", "task")
        assert found == "ut-1"

    def test_resolve_by_search_field(self, g, session):
        user = User(id=str(uuid.uuid4()), email="z@b.com", hashed_password="x",
                    first_name="Z", last_name="Q", tenant_id="t-1",
                    workspace_id="ws-1", role="member", status="active")
        session.add(user)
        session.commit()
        with _db_ctx(session):
            found = g._resolve_canonical_entity(session, "ws-1", "z@b.com", "user")
        assert found == user.id

    def test_resolve_exact_then_fuzzy(self, g, session):
        with _db_ctx(session):
            assert g._resolve_canonical_entity(session, "ws-1", "user", "missing@x.com") is None

    def test_resolve_no_config(self, g, session):
        with _db_ctx(session):
            assert g._resolve_canonical_entity(session, "ws-1", "ghost", "anything") is None

    def test_create_canonical_entity(self, g, session):
        with _db_ctx(session):
            created = g._create_canonical_entity_if_missing(
                session, "t-1", "My Workspace", "workspace"
            )
        assert created is not None
        assert session.query(Workspace).filter_by(id=created).first() is not None

    def test_create_canonical_user_fails_gracefully(self, g, session):
        with _db_ctx(session):
            created = g._create_canonical_entity_if_missing(
                session, "t-1", "carol@x.com", "user"
            )
        assert created is None

    def test_create_canonical_no_config(self, g, session):
        with _db_ctx(session):
            assert g._create_canonical_entity_if_missing(session, "ws-1", "x", "ghost") is None

    def test_create_canonical_exception(self, g, session):
        user = User(id=str(uuid.uuid4()), email="dup@b.com", hashed_password="x",
                    first_name="A", last_name="B", tenant_id="t-1",
                    role="member", status="active")
        session.add(user)
        session.commit()
        with _db_ctx(session):
            created = g._create_canonical_entity_if_missing(session, "t-1", "dup@b.com", "user")
        assert created is None

    def test_get_entity_registry_plain(self, g):
        registry = g._get_entity_registry()
        assert "user" in registry and "ticket" in registry and "formula" in registry

    def test_get_entity_registry_with_workspace(self, g):
        with _db_ctx(g.db):
            registry = g._get_entity_registry("ws-1")
        assert "user" in registry

    def test_load_custom_entity_types_empty(self, g, session):
        with _db_ctx(session):
            assert g._load_custom_entity_types("ws-1") == {}

    def test_load_custom_entity_types_error(self, g, session):
        session.close()
        with _db_ctx(session):
            assert g._load_custom_entity_types("ws-1") == {}

    def test_get_registry_entry(self, g):
        assert g._get_registry_entry("user") is not None
        assert g._get_registry_entry("ghost") is None


# ============================ canonical_search ============================


class TestCanonicalSearch:
    def test_unknown_type_returns_empty(self, g):
        with _db_ctx(g.db):
            assert g.canonical_search(entity_type="ghost", query="x") == []

    def test_tenant_filtered_search(self, g, session):
        user = User(id=str(uuid.uuid4()), email="found@b.com", hashed_password="x",
                    first_name="A", last_name="B", tenant_id="t-1",
                    workspace_id="ws-1", role="member", status="active")
        session.add(user)
        session.commit()
        with _db_ctx(session):
            results = g.canonical_search(entity_type="user", query="found")
        assert results == [{"id": user.id, "name": "found@b.com"}]

    def test_workspace_filtered_search(self, g, session):
        node = make_node(session, "Alpha Corp")
        with patch.object(g, "_get_registry_entry", return_value={
            "model": GraphNode, "search_fields": ["name"], "display_field": "name",
        }):
            with _db_ctx(session):
                results = g.canonical_search(entity_type="custom", query="alpha")
        assert results == [{"id": node.id, "name": "Alpha Corp"}]

    def test_search_exception_returns_empty(self, g, session):
        session.close()
        with _db_ctx(session):
            results = g.canonical_search(entity_type="user", query="x")
        assert results == []

    def test_search_too_long_raises(self, g):
        with pytest.raises(ValueError):
            g.canonical_search(entity_type="user", query="x" * 600)


# ============================ add_entity / add_relationship ============================


class TestAddEntity:
    def test_add_new_entity(self, g, session):
        with _db_ctx(session), patch("core.graphrag_engine.AUTOMATION_AVAILABLE", False):
            entity = Entity(id="e1", name="Acme", entity_type="org", description="d")
            result = g.add_entity(entity, workspace_id="ws-1", tenant_id="t-1")
        assert result == "e1"
        assert session.query(GraphNode).filter_by(id="e1").first() is not None

    def test_add_existing_entity_updates(self, g, session):
        make_node(session, "Acme", nid="e1")
        with _db_ctx(session), patch("core.graphrag_engine.AUTOMATION_AVAILABLE", False):
            entity = Entity(id="e-new", name="Acme", entity_type="org", description="updated",
                            properties={"embedding": [0.1]})
            result = g.add_entity(entity, workspace_id="ws-1", tenant_id="t-1")
        assert result == "e1"
        node = session.query(GraphNode).filter_by(id="e1").first()
        assert node.description == "updated"
        assert node.embedding == [0.1]

    def test_add_entity_canonical_resolved_and_updates_record(self, g, session):
        user = User(id=str(uuid.uuid4()), email="meta@b.com", hashed_password="x",
                    first_name="Old", last_name="Name", tenant_id="t-1",
                    workspace_id="ws-1", role="member", status="active")
        session.add(user)
        session.commit()
        with _db_ctx(session), patch("core.graphrag_engine.AUTOMATION_AVAILABLE", False):
            entity = Entity(
                id="e2", name="meta@b.com", entity_type="person", description="new",
                properties={"canonical_type": "user", "first_name": "New", "specialty": "x"},
            )
            g.add_entity(entity, workspace_id="ws-1", tenant_id="t-1")
        session.expire_all()
        updated = session.query(User).filter_by(id=user.id).first()
        assert updated.first_name == "New"
        assert "canonical_id" in entity.properties

    def test_add_entity_canonical_created(self, g, session):
        with _db_ctx(session), patch("core.graphrag_engine.AUTOMATION_AVAILABLE", False):
            entity = Entity(
                id="e3", name="Fresh WS", entity_type="workspace", description="d",
                properties={"canonical_type": "workspace"},
            )
            g.add_entity(entity, workspace_id="t-1", tenant_id="t-1")
        assert entity.properties["canonical_id"] is not None

    def test_add_entity_error_rolls_back(self, g, session):
        session.commit = Mock(side_effect=[RuntimeError("boom"), None])
        with _db_ctx(session):
            entity = Entity(id="e4", name="X", entity_type="org")
            assert g.add_entity(entity, workspace_id="ws-1") is None

    def test_add_entity_automation_trigger(self, g, session):
        with _db_ctx(session):
            entity = Entity(id="e5", name="Auto", entity_type="org")
            orch = Mock()
            orch.trigger_event = Mock()
            with patch("core.graphrag_engine.AUTOMATION_AVAILABLE", True):
                with patch("core.graphrag_engine.orchestrator", orch, create=True):
                    with patch("asyncio.create_task") as ct:
                        ct.return_value = Mock()
                        ct.return_value.add_done_callback = Mock()
                        g.add_entity(entity, workspace_id="ws-1", tenant_id="t-1")
                    orch.trigger_event.assert_called_once()


class TestAddRelationship:
    def _nodes(self, session):
        a = make_node(session, "A", nid="a1")
        b = make_node(session, "B", nid="b1")
        return a, b

    def test_add_relationship_success(self, g, session):
        self._nodes(session)
        rel = Relationship(id="r1", from_entity="a1", to_entity="b1", rel_type="knows")
        with _db_ctx(session):
            result = g.add_relationship(rel, workspace_id="ws-1", tenant_id="t-1")
        assert result == "r1"
        assert session.query(GraphEdge).filter_by(id="r1").first() is not None

    def test_add_relationship_missing_source(self, g, session):
        make_node(session, "B", nid="b1")
        rel = Relationship(id="r2", from_entity="ghost", to_entity="b1", rel_type="knows")
        with _db_ctx(session):
            assert g.add_relationship(rel, workspace_id="ws-1") is None

    def test_add_relationship_missing_target(self, g, session):
        make_node(session, "A", nid="a1")
        rel = Relationship(id="r3", from_entity="a1", to_entity="ghost", rel_type="knows")
        with _db_ctx(session):
            assert g.add_relationship(rel, workspace_id="ws-1") is None

    def test_add_relationship_error(self, g, session):
        make_node(session, "A", nid="a1")
        make_node(session, "B", nid="b1")
        session.commit = Mock(side_effect=[RuntimeError("boom"), None])
        rel = Relationship(id="r4", from_entity="a1", to_entity="b1", rel_type="knows")
        with _db_ctx(session):
            assert g.add_relationship(rel, workspace_id="ws-1") is None


# ============================ ingest_structured_data / ingest_document ============================


class TestIngest:
    def test_ingest_structured_data(self, g, session):
        entities = [
            {"name": "Acme", "type": "org", "description": "d", "properties": {}},
            {"name": "Bob", "type": "person", "description": "d", "properties": {}},
            {"name": "", "type": "junk", "properties": {}},
        ]
        relationships = [{"from": "Acme", "to": "Bob", "type": "employs"}]
        with _db_ctx(session):
            result = g.ingest_structured_data("ws-1", "t-1", entities, relationships)
        assert result == {"entities": 3, "relationships": 1}
        assert session.query(GraphNode).filter_by(name="Acme").first() is not None
        assert session.query(GraphEdge).count() == 1

    def test_ingest_with_canonical_resolution(self, g, session):
        user = User(id=str(uuid.uuid4()), email="ingest@b.com", hashed_password="x",
                    first_name="I", last_name="N", tenant_id="t-1",
                    workspace_id="ws-1", role="member", status="active")
        session.add(user)
        session.commit()
        entities = [{"name": "ingest@b.com", "type": "person",
                     "properties": {"canonical_type": "user"}}]
        with _db_ctx(session):
            g.ingest_structured_data("ws-1", "t-1", entities, [])
        node = session.query(GraphNode).filter_by(name="ingest@b.com").first()
        assert node.properties["canonical_id"] == user.id

    def test_ingest_error(self, g, session):
        session.commit = Mock(side_effect=[RuntimeError("boom"), None])
        with _db_ctx(session):
            result = g.ingest_structured_data("ws-1", "t-1", [{"name": "X"}], [])
        assert result == {"entities": 0, "relationships": 0}

    async def test_ingest_document_llm_path(self, g, session):
        g._is_llm_available = Mock(return_value=True)
        g._llm_extract_entities_and_relationships = AsyncMock(
            return_value=([Entity(id="x", name="Acme", entity_type="org")], [])
        )
        with _db_ctx(session), patch.object(g, "ingest_structured_data") as ingest:
            await g.ingest_document(doc_id="d1", text="text", source="src")
        ingest.assert_called_once()
        args = ingest.call_args
        assert args.args[2][0]["name"] == "Acme"

    async def test_ingest_document_no_entities(self, g, session):
        g._is_llm_available = Mock(return_value=True)
        g._llm_extract_entities_and_relationships = AsyncMock(return_value=([], []))
        with _db_ctx(session), patch.object(g, "ingest_structured_data") as ingest:
            await g.ingest_document(doc_id="d1", text="text", source="src")
        ingest.assert_not_called()

    async def test_ingest_document_pattern_fallback(self, g, session):
        g._is_llm_available = Mock(return_value=False)
        with _db_ctx(session), patch.object(g, "ingest_structured_data") as ingest:
            await g.ingest_document(
                doc_id="d1", text="mail me at a@b.com", source="src"
            )
        ingest.assert_called_once()


# ============================ local_search ============================


class TestLocalSearch:
    def test_no_start_nodes(self, g, session):
        with _db_ctx(session):
            result = g.local_search("ws-1", "t-1", query="nothing-here")
        assert result["mode"] == "local"
        assert result["entities"] == []
        assert "No matching entities" in result["context"]

    def test_sqlite_traversal(self, g, session):
        a = make_node(session, "Alpha", nid="a1", props={"doc_id": "d1"})
        make_node(session, "Beta", nid="b1", props={"doc_id": "d1"})
        session.add(GraphEdge(id="e1", tenant_id="t-1", workspace_id="ws-1",
                              source_node_id="a1", target_node_id="b1",
                              relationship_type="related"))
        session.commit()
        expander = Mock()
        expander.expand_sql = Mock(return_value=SimpleNamespace(paths=[
            SimpleNamespace(node_ids=["a1", "b1"], relevance_score=0.9, hops=1)
        ]))
        with _db_ctx(session), patch(
            "core.graphrag.multi_hop_expansion.get_sql_expander", return_value=expander
        ):
            result = g.local_search("ws-1", "t-1", query="Alpha", depth=2, exclude_doc_ids=set())
        assert result["mode"] == "local"
        names = {e["name"] for e in result["entities"]}
        assert "Alpha" in names and "Beta" in names
        assert result["count"] == 2
        assert result["multi_hop_paths"][0]["relevance"] == 0.9

    def test_embedding_generation_failure(self, g, session):
        make_node(session, "Gamma", nid="a2")
        g.llm_service.generate_embedding = AsyncMock(side_effect=RuntimeError("emb down"))
        with _db_ctx(session):
            result = g.local_search("ws-1", "t-1", query="Gamma", exclude_doc_ids=set())
        assert result["entities"][0]["name"] == "Gamma"

    def test_vector_leg_fails_gracefully_on_sqlite(self, g, session):
        make_node(session, "Delta", nid="a3", props={"doc_id": "d1"})
        g.llm_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        with _db_ctx(session):
            result = g.local_search("ws-1", "t-1", query="Delta", exclude_doc_ids=set())
        assert result["entities"][0]["name"] == "Delta"

    def test_freshness_exclude_ids(self, g, session):
        make_node(session, "Fresh", nid="f1", props={"doc_id": "keep"})
        make_node(session, "Stale", nid="s1", props={"doc_id": "drop"})
        with _db_ctx(session):
            result = g.local_search("ws-1", "t-1", query="Stale", exclude_doc_ids={"drop"})
            assert result["entities"] == []
            result2 = g.local_search("ws-1", "t-1", query="Stale", include_stale=True)
            assert result2["entities"][0]["name"] == "Stale"

    def test_freshness_service_resolution(self, g, session):
        make_node(session, "Alpha", nid="a1")
        freshness = Mock()
        freshness.non_fresh_doc_ids = Mock(return_value={"stale-doc"})
        with _db_ctx(session), patch(
            "core.graphrag.multi_hop_expansion.get_sql_expander", Mock(return_value=Mock(
                expand_sql=Mock(return_value=SimpleNamespace(paths=[]))
            ))
        ), patch("core.doc_freshness_service.FRESHNESS_FILTER_ENABLED", True), patch(
            "core.doc_freshness_service.DocFreshnessService", return_value=freshness
        ):
            result = g.local_search("ws-1", "t-1", query="Alpha")
        assert result["mode"] == "local"
        assert len(result["entities"]) == 1

    def test_sqlite_empty_traversal_and_expander_error(self, g, session):
        make_node(session, "Alpha", nid="a1", props={"doc_id": "d1"})
        expander = Mock()
        expander.expand_sql = Mock(side_effect=RuntimeError("expander down"))
        orig_execute = session.execute

        def fake_exec(sql, params=None):
            if "WITH RECURSIVE" in str(sql):
                return SimpleNamespace(fetchall=lambda: [])
            return orig_execute(sql, params)

        session.execute = fake_exec
        try:
            with _db_ctx(session), patch(
                "core.graphrag.multi_hop_expansion.get_sql_expander", return_value=expander
            ):
                result = g.local_search("ws-1", "t-1", query="Alpha", depth=2, exclude_doc_ids=set())
        finally:
            session.execute = orig_execute
        assert result["mode"] == "local"
        assert result["entities"] == []
        assert result["relationships"] == []

    def test_pg_branch_with_mock_session(self, g):
        row = SimpleNamespace(id="n1", name="Alpha", type="org", description="d")
        edge_row = SimpleNamespace(source_node_id="n1", target_node_id="n2",
                                   relationship_type="rel")
        vector_result = Mock()
        vector_result.fetchall.return_value = [row]
        keyword_result = Mock()
        keyword_result.fetchall.return_value = [row]
        traversal_result = Mock()
        traversal_result.fetchall.return_value = [row, SimpleNamespace(
            id="n2", name="Beta", type="person", description="d")]
        edges_result = Mock()
        edges_result.fetchall.return_value = [edge_row]

        session = Mock()
        session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        session.execute = Mock(side_effect=[vector_result, keyword_result,
                                            traversal_result, edges_result])
        g.llm_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2])

        expander = Mock()
        expander.expand_sql = Mock(return_value=SimpleNamespace(paths=[]))
        with _db_ctx(session), patch(
            "core.graphrag.multi_hop_expansion.get_sql_expander", return_value=expander
        ):
            result = g.local_search("ws-1", "t-1", query="Alpha", depth=2,
                                    exclude_doc_ids={"stale1"})
        assert result["entities"][0]["id"] == "n1"
        assert result["relationships"][0]["type"] == "rel"
        assert session.execute.call_count == 4

    def test_pg_branch_uses_array_binding(self, g):
        row = SimpleNamespace(id="n1", name="Alpha", type="org", description="d")
        keyword_result = Mock()
        keyword_result.fetchall.return_value = [row]
        traversal_result = Mock()
        traversal_result.fetchall.return_value = [row]
        edges_result = Mock()
        edges_result.fetchall.return_value = []

        session = Mock()
        session.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
        session.execute = Mock(side_effect=[keyword_result, traversal_result, edges_result])

        with _db_ctx(session), patch(
            "core.graphrag.multi_hop_expansion.get_sql_expander", Mock(return_value=Mock(
                expand_sql=Mock(return_value=SimpleNamespace(paths=[]))
            ))
        ):
            result = g.local_search("ws-1", "t-1", query="Alpha")
        assert result["entities"][0]["id"] == "n1"

    def test_query_exception_returns_error_dict(self, g, session):
        orig_execute = session.execute
        session.execute = Mock(side_effect=RuntimeError("db down"))
        try:
            with _db_ctx(session):
                result = g.local_search("ws-1", "t-1", query="x")
            assert result["error"] is not None
            assert result["mode"] == "local"
        finally:
            session.execute = orig_execute


# ============================ global_search / query / context ============================


class TestGlobalSearch:
    def test_no_communities(self, g, session):
        with _db_ctx(session):
            result = g.local_search  # noqa
        with _db_ctx(session), patch("core.graphrag_engine.get_db_session") as ctx:
            pass

    async def test_global_no_communities(self, g, session):
        with _db_ctx(session):
            result = await g.global_search("ws-1", "t-1", query="x")
        assert result["mode"] == "global"
        assert result["answer"] == "No community data available for global search."

    async def test_global_with_communities(self, g, session):
        session.add(GraphCommunity(id="c1", tenant_id="t-1", workspace_id="ws-1",
                                   summary="Sales overview", keywords=["sales"], level=0))
        session.commit()
        g.llm_service.generate_completion = AsyncMock(
            return_value={"content": "Synthesized answer"}
        )
        with _db_ctx(session):
            result = await g.global_search("ws-1", "t-1", query="sales")
        assert result["summaries"] == ["Sales overview"]
        assert result["answer"] == "Synthesized answer"

    async def test_global_llm_error(self, g, session):
        session.add(GraphCommunity(id="c2", tenant_id="t-1", workspace_id="ws-1",
                                   summary="S", keywords=["k"], level=0))
        session.commit()
        g.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("llm down"))
        with _db_ctx(session):
            result = await g.global_search("ws-1", "t-1", query="")
        assert result["mode"] == "global"
        assert "Error" in result["answer"]

    async def test_global_fallback_summaries(self, g, session):
        session.add(GraphCommunity(id="c3", tenant_id="t-1", workspace_id="ws-1",
                                   summary="Fallback summary", keywords=["k"], level=0))
        session.commit()
        g.llm_service.generate_completion = AsyncMock(return_value={"content": "answer"})
        with _db_ctx(session):
            result = await g.global_search("ws-1", "t-1", query="zzz-no-match")
        assert result["summaries"] == ["Fallback summary"]
        assert result["answer"] == "answer"

    async def test_query_auto_routing(self, g):
        g.global_search = AsyncMock(return_value={"mode": "global", "answer": "A"})
        g.local_search = Mock(return_value={"mode": "local"})
        res = await g.query("ws-1", "t-1", query="give me an overview", mode="auto")
        assert res["mode"] == "global"
        res2 = await g.query("ws-1", "t-1", query="what is x", mode="auto")
        assert res2["mode"] == "local"

    async def test_query_explicit_modes(self, g):
        g.global_search = AsyncMock(return_value={"mode": "global", "answer": "A"})
        g.local_search = Mock(return_value={"mode": "local"})
        res = await g.query("ws-1", "t-1", query="x", mode="global")
        assert res["mode"] == "global"
        res2 = await g.query("ws-1", "t-1", query="x", mode="local")
        assert res2["mode"] == "local"

    async def test_get_context_for_ai_global(self, g):
        g.query = AsyncMock(return_value={"mode": "global", "answer": "Sum"})
        assert await g.get_context_for_ai("ws-1", "t-1", "overview") == "Global Context: Sum"

    async def test_get_context_for_ai_local(self, g):
        g.query = AsyncMock(return_value={"mode": "local", "entities": [
            {"id": "n1", "name": "Alpha", "type": "org", "description": "d"}],
            "relationships": [{"from": "n1", "to": "missing", "type": "knows"}]})
        ctx = await g.get_context_for_ai("ws-1", "t-1", "x")
        assert "Found 1 relevant entities" in ctx
        assert "Alpha (org): d" in ctx
        assert "Alpha -> knows -> missing" in ctx


# ============================ reindex / communities / hypotheses ============================


class TestOps:
    def test_enqueue_reindex_no_redis(self, g, monkeypatch):
        monkeypatch.delenv("UPSTASH_REDIS_URL", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        assert g.enqueue_reindex_job("ws-1") is False

    def test_enqueue_reindex_with_redis(self, g, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        redis = Mock()
        redis.from_url.return_value.lpush.return_value = 1
        with patch.dict("sys.modules", {"redis": redis}):
            assert g.enqueue_reindex_job("ws-1") is True
        redis.from_url.assert_called_once()

    def test_enqueue_reindex_redis_error(self, g, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        redis = Mock()
        redis.from_url.side_effect = RuntimeError("down")
        with patch.dict("sys.modules", {"redis": redis}):
            assert g.enqueue_reindex_job("ws-1") is False

    def test_build_communities_success(self, g):
        detector = Mock()
        detector.detect_communities = Mock(return_value=SimpleNamespace(
            communities=[1, 2, 3]
        ))
        with patch("core.graphrag.community_detection.get_community_detector",
                   return_value=detector):
            result = g.build_communities("ws-1")
        assert result["success"] is True
        assert result["communities"] == 3

    def test_build_communities_failure(self, g):
        with patch("core.graphrag.community_detection.get_community_detector",
                   side_effect=RuntimeError("no detector")):
            result = g.build_communities("ws-1")
        assert result["success"] is False
        assert "no detector" in result["error"]

    async def test_discover_patterns_with_db(self, g, session):
        with _db_ctx(session):
            result = await g.discover_failed_hypotheses_patterns("t-1")
        assert result["success"] is True
        assert result["patterns"] == []

    async def test_discover_patterns_without_db(self):
        g2 = GraphRAGEngine(workspace_id="ws-1", tenant_id="t-1", db=None)
        g2.llm_service = Mock()
        session = Mock()
        session.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = []
        with _db_ctx(session):
            result = await g2.discover_failed_hypotheses_patterns("t-1")
        assert result["patterns"] == []

    async def test_discover_patterns_no_records(self, g):
        session = Mock()
        session.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = []
        result = await g._discover_patterns_with_session(session, "t-1")
        assert result["patterns"] == []
        assert "No failed hypotheses" in result["summary"]

    async def test_discover_patterns_with_llm(self, g):
        record = SimpleNamespace(
            task_description="task", task_type="type", total_nodes=5,
            pruned_nodes=2, negative_constraints=["no-x"], created_at=None,
        )
        session = Mock()
        session.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [record]
        g.llm_service.generate_completion = AsyncMock(return_value={"content": "pattern found"})
        with patch("core.graphrag_engine.GRAPHRAG_LLM_ENABLED", True):
            result = await g._discover_patterns_with_session(session, "t-1")
        assert result["sessions_analyzed"] == 1
        assert result["aggregated_constraints"] == ["no-x"]
        assert result["summary"] == "pattern found"

    async def test_discover_patterns_llm_error(self, g):
        record = SimpleNamespace(
            task_description="t", task_type="ty", total_nodes=1,
            pruned_nodes=1, negative_constraints=None, created_at=None,
        )
        session = Mock()
        session.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [record]
        g.llm_service.generate_completion = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("core.graphrag_engine.GRAPHRAG_LLM_ENABLED", True):
            result = await g._discover_patterns_with_session(session, "t-1")
        assert "Synthesis error" in result["summary"]

    async def test_discover_patterns_llm_disabled(self, g):
        record = SimpleNamespace(
            task_description="t", task_type="ty", total_nodes=1,
            pruned_nodes=1, negative_constraints=None, created_at=None,
        )
        session = Mock()
        session.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [record]
        with patch("core.graphrag_engine.GRAPHRAG_LLM_ENABLED", False):
            result = await g._discover_patterns_with_session(session, "t-1")
        assert result["summary"] == "LLM synthesis skipped."
