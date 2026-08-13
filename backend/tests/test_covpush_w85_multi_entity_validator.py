# -*- coding: utf-8 -*-
"""Coverage wave 85 — core/multi_entity_validator (never-wave-tested).

Covers GraphRAG multi-entity relationship validation:
- validate_relationship_exists: valid edge (with/without relationship_type
  filter); missing node a/b -> ValueError; no edge -> ValueError; workspace
  isolation (edge in another workspace is invisible).
- get_relationship_metadata: full metadata incl. description from properties;
  edge without properties -> no description key; missing node/edge -> {}.

Real in-memory SQLite GraphNode/GraphEdge rows (no network, zero LLM spend).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import GraphEdge, GraphNode  # noqa: F401 (register models)
from core.multi_entity_validator import MultiEntityValidator


@pytest.fixture()
def db():
    """In-memory SQLite session with the full schema."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _node(db, node_id, type_, workspace="ws-1", name=None):
    node = GraphNode(id=node_id, workspace_id=workspace, type=type_,
                     name=name or f"n-{type_}")
    db.add(node)
    db.commit()
    return node


def _edge(db, edge_id="e-1", source="a", target="b", rel="relates_to",
          weight=1.5, props=None, workspace="ws-1"):
    edge = GraphEdge(id=edge_id, workspace_id=workspace,
                     source_node_id=source, target_node_id=target,
                     relationship_type=rel, weight=weight,
                     properties=props)
    db.add(edge)
    db.commit()
    return edge


class TestValidateRelationshipExists:
    def test_valid_relationship(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        _edge(db, source="a", target="b", rel="manages")
        assert MultiEntityValidator(db, "ws-1").validate_relationship_exists(
            "person", "project") is True

    def test_valid_relationship_with_type_filter(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        _edge(db, source="a", target="b", rel="manages")
        assert MultiEntityValidator(db, "ws-1").validate_relationship_exists(
            "person", "project", relationship_type="manages") is True

    def test_type_filter_mismatch_raises(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        _edge(db, source="a", target="b", rel="manages")
        with pytest.raises(ValueError, match="No relationship found"):
            MultiEntityValidator(db, "ws-1").validate_relationship_exists(
                "person", "project", relationship_type="blocks")

    def test_node_a_missing_raises(self, db):
        _node(db, "b", "project")
        with pytest.raises(ValueError, match="Entity types not indexed"):
            MultiEntityValidator(db, "ws-1").validate_relationship_exists(
                "person", "project")

    def test_node_b_missing_raises(self, db):
        _node(db, "a", "person")
        with pytest.raises(ValueError, match="Entity types not indexed"):
            MultiEntityValidator(db, "ws-1").validate_relationship_exists(
                "person", "project")

    def test_no_edge_raises(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        with pytest.raises(ValueError, match="No relationship found"):
            MultiEntityValidator(db, "ws-1").validate_relationship_exists(
                "person", "project")

    def test_workspace_isolation_no_edge(self, db):
        _node(db, "a", "person", workspace="ws-1")
        _node(db, "b", "project", workspace="ws-1")
        _edge(db, source="a", target="b", workspace="ws-2")
        with pytest.raises(ValueError, match="No relationship found"):
            MultiEntityValidator(db, "ws-1").validate_relationship_exists(
                "person", "project")


class TestGetRelationshipMetadata:
    def test_full_metadata_with_description(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        _edge(db, source="a", target="b", rel="manages", weight=2.0,
              props={"description": "Alice leads project"})
        meta = MultiEntityValidator(db, "ws-1").get_relationship_metadata(
            "person", "project")
        assert meta == {
            "relationship_type": "manages",
            "weight": 2.0,
            "properties": {"description": "Alice leads project"},
            "description": "Alice leads project",
        }

    def test_metadata_without_properties(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        _edge(db, source="a", target="b", rel="manages", props=None)
        meta = MultiEntityValidator(db, "ws-1").get_relationship_metadata(
            "person", "project")
        assert meta["relationship_type"] == "manages"
        assert meta["properties"] == {}
        assert "description" not in meta

    def test_missing_node_returns_empty(self, db):
        _node(db, "b", "project")
        assert MultiEntityValidator(db, "ws-1").get_relationship_metadata(
            "person", "project") == {}

    def test_missing_edge_returns_empty(self, db):
        _node(db, "a", "person")
        _node(db, "b", "project")
        assert MultiEntityValidator(db, "ws-1").get_relationship_metadata(
            "person", "project") == {}
